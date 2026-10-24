#!/usr/bin/env python3
# ==============================================================================
# Vault Automated Initialization, Unsealing & Secret Seeding Provisioner
# ==============================================================================

import argparse
import json
import os
import re
import secrets
import stat
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))

import http_client

VAULT_URL = os.environ.get("VAULT_URL", "https://localhost:8201")
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if "SSL_CERT_FILE" not in os.environ:
    _ca_file = os.path.join(REPO_ROOT, "traefik", "certs", "trust.crt")
    if os.path.exists(_ca_file):
        os.environ["SSL_CERT_FILE"] = _ca_file
KEYS_FILE = ".vault_keys.json"
AGENT_ROLE = "llm-stack-vault-agent"
SECRETS_DIRECTORY = "vault/secrets_ram"
RAM_PREFIX = "/dev/shm/llm-stack-vault-secrets-"


def expected_ram_path():
    """Return the per-instance path without trusting arbitrary environment paths."""
    instance_id = os.environ.get("SECRETS_RAM_ID", "")
    if not re.fullmatch(r"[0-9a-f]{16}", instance_id):
        raise RuntimeError("SECRETS_RAM_ID must be a generated 16-character hex ID")
    return f"{RAM_PREFIX}{instance_id}"


def require_ram_link():
    """Reject a missing or redirected link before touching any runtime secret."""
    link = os.path.abspath(SECRETS_DIRECTORY)
    target = expected_ram_path()
    if not os.path.islink(link) or os.readlink(link) != target:
        raise RuntimeError("Vault secret directory must link to its private RAM path")
    if os.path.realpath(link) != target:
        raise RuntimeError("Vault RAM path must not redirect to another location")
    return target


def prepare_ram_link():
    """Replace only an empty legacy mountpoint; never touch existing secret data."""
    link = os.path.abspath(SECRETS_DIRECTORY)
    target = expected_ram_path()
    if os.path.islink(link):
        require_ram_link()
    elif os.path.lexists(link):
        if not os.path.isdir(link) or os.listdir(link):
            raise RuntimeError("Existing Vault secret directory is nonempty; migration requires a separate CAB")
        os.rmdir(link)
        os.symlink(target, link)
    else:
        os.symlink(target, link)
    print("[Vault] Private RAM link prepared; no secret was rendered.")


def ensure_ram_directory():
    """Recreate an ephemeral target after reboot, then validate ownership and fs."""
    target = require_ram_link()
    created = False
    if not os.path.lexists(target):
        try:
            os.mkdir(target, 0o700)
            created = True
        except FileExistsError:
            pass
    if created and os.geteuid() == 0:
        os.chown(target, int(os.environ["SECRETS_RAM_UID"]), int(os.environ["SECRETS_RAM_GID"]))
    require_ram_directory()


def require_ram_directory():
    """Reject a secrets path backed by persistent storage or broad permissions."""
    path = require_ram_link()
    if not os.path.isdir(path):
        raise RuntimeError("Vault secret directory does not exist")
    directory_stat = os.stat(path)
    if directory_stat.st_uid != int(os.environ["SECRETS_RAM_UID"]):
        raise RuntimeError("Vault secret directory has an unexpected owner")
    if stat.S_IMODE(directory_stat.st_mode) & 0o077:
        raise RuntimeError("Vault secret directory must be owner-only")
    best_mount = ""
    filesystem = None
    with open("/proc/self/mountinfo", encoding="utf-8") as mounts:
        for line in mounts:
            fields = line.split()
            mountpoint = fields[4].replace("\\040", " ")
            if (path == mountpoint or path.startswith(mountpoint.rstrip("/") + "/")) and len(mountpoint) > len(best_mount):
                separator = fields.index("-")
                best_mount = mountpoint
                filesystem = fields[separator + 1]
    if filesystem != "tmpfs":
        raise RuntimeError("Vault secret directory must be mounted on tmpfs")
    return path


def write_agent_credential(path, value):
    """Publish an Agent-only credential atomically without printing its value."""
    uid = int(os.environ["SECRETS_RAM_UID"])
    gid = int(os.environ["SECRETS_RAM_GID"])
    if os.geteuid() not in (0, uid):
        raise RuntimeError("Provisioner cannot own Vault Agent credentials")
    temporary = f"{path}.{secrets.token_hex(8)}.tmp"
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        if os.geteuid() == 0:
            os.fchown(descriptor, uid, gid)
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            output.write(value)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def configure_agent_approle(root_token):
    """Grant Vault Agent read-only KV access without sharing a root token."""
    directory = require_ram_directory()
    if os.path.exists(os.path.join(directory, "vault_agent_token")):
        raise RuntimeError("Legacy root token remains in the shared secret directory")
    headers = {"X-Vault-Token": root_token}
    policy = 'path "secret/data/llm-stack/*" { capabilities = ["read"] }\n'
    response = http_client.put(
        f"{VAULT_URL}/v1/sys/policies/acl/{AGENT_ROLE}",
        headers=headers, json={"policy": policy},
    )
    response.raise_for_status()
    mounts = http_client.get(f"{VAULT_URL}/v1/sys/auth", headers=headers)
    mounts.raise_for_status()
    if "approle/" not in mounts.json():
        response = http_client.post(
            f"{VAULT_URL}/v1/sys/auth/approle", headers=headers,
            json={"type": "approle"},
        )
        response.raise_for_status()
    response = http_client.post(
        f"{VAULT_URL}/v1/auth/approle/role/{AGENT_ROLE}", headers=headers,
        json={
            "bind_secret_id": True,
            "secret_id_num_uses": 0,
            "secret_id_ttl": 0,
            "token_policies": [AGENT_ROLE],
            "token_no_default_policy": True,
            "token_type": "service",
            "period": "1h",
        },
    )
    response.raise_for_status()
    role_response = http_client.get(
        f"{VAULT_URL}/v1/auth/approle/role/{AGENT_ROLE}/role-id", headers=headers,
    )
    role_response.raise_for_status()
    role_id = role_response.json().get("data", {}).get("role_id")
    if not role_id:
        raise RuntimeError("Vault AppRole has no role ID")
    secret_response = http_client.post(
        f"{VAULT_URL}/v1/auth/approle/role/{AGENT_ROLE}/secret-id",
        headers=headers, json={},
    )
    secret_response.raise_for_status()
    secret_id = secret_response.json().get("data", {}).get("secret_id")
    if not secret_id:
        raise RuntimeError("Vault AppRole has no secret ID")
    write_agent_credential(os.path.join(directory, ".agent-role-id"), role_id)
    write_agent_credential(os.path.join(directory, ".agent-secret-id"), secret_id)
    print("[Vault] Scoped Agent AppRole credentials written to tmpfs.")


def read_env(path='.env'):
    env = {}
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                m = re.match(r'^([A-Z_0-9]+)=(.*)$', line)
                if m:
                    env[m.group(1)] = m.group(2).strip('"\'')
    return env


def load_env_defaults():
    env = read_env()
    for key in ("SECRETS_RAM_ID", "SECRETS_RAM_UID", "SECRETS_RAM_GID", "SECRETS_RENDER_GID"):
        if key not in os.environ and key in env:
            os.environ[key] = env[key]


def wait_for_readiness():
    print("[Vault] Waiting for Vault HTTP server to be ready on port 8201...")
    for _ in range(15):
        try:
            r = http_client.get(f"{VAULT_URL}/v1/sys/init", timeout=2)
            if r.status_code in (200, 400, 500):
                print("[Vault] Server is reachable!")
                return
        except Exception:
            pass
        time.sleep(1)
    print("[Vault] Warning: Vault did not become ready in 15s")


def init_and_unseal():
    wait_for_readiness()
    r_status = http_client.get(f"{VAULT_URL}/v1/sys/init")
    is_init = r_status.json().get('initialized', False)

    if not is_init:
        print("[Vault] Initializing Vault...")
        r_init = http_client.post(f"{VAULT_URL}/v1/sys/init", json={"secret_shares": 1, "secret_threshold": 1})
        keys_data = r_init.json()
        if r_init.status_code != 200 or not keys_data.get('keys'):
            print(f"[Vault] Error: initialization failed (HTTP {r_init.status_code}): {keys_data.get('errors')}")
            sys.exit(1)
        with open(KEYS_FILE, 'w') as f:
            json.dump(keys_data, f, indent=2)
        os.chmod(KEYS_FILE, 0o600)
        print(f"[Vault] Initialized! Keys written to {KEYS_FILE}")
    else:
        print("[Vault] Already initialized.")

    if not os.path.exists(KEYS_FILE):
        print(f"[Vault] Error: {KEYS_FILE} not found!")
        sys.exit(1)

    with open(KEYS_FILE) as f:
        keys = json.load(f)

    unseal_key = keys.get('keys', [''])[0]
    root_token = keys.get('root_token', '')

    # 2. Unseal if sealed
    r_health = http_client.get(f"{VAULT_URL}/v1/sys/health")
    if r_health.status_code == 503 or r_health.json().get('sealed', True):
        print("[Vault] Vault is sealed. Unsealing...")
        r_unseal = http_client.post(f"{VAULT_URL}/v1/sys/unseal", json={"key": unseal_key})
        assert not r_unseal.json().get('sealed', True), "Failed to unseal Vault!"
        print("[Vault] Unsealed successfully!")
    else:
        print("[Vault] Vault is already unsealed.")

    return root_token


def read_account_passwords():
    env = read_env()
    account_passwords = {}
    for account in ('ALICE', 'BOB'):
        key = f'{account}_PASSWORD'
        value = env.get(key, '')
        if not value or 'change_me' in value.lower():
            raise RuntimeError(f'{key} must be generated by setup.sh before Vault provisioning')
        account_passwords[key] = value
    return account_passwords


def write_account_passwords(root_token, account_passwords):
    response = http_client.post(
        f"{VAULT_URL}/v1/secret/data/llm-stack/authentik",
        headers={"X-Vault-Token": root_token},
        json={"data": account_passwords},
    )
    response.raise_for_status()


def seed_authentik_accounts_only(root_token):
    account_passwords = read_account_passwords()
    headers = {"X-Vault-Token": root_token}
    response = http_client.get(f"{VAULT_URL}/v1/sys/mounts", headers=headers)
    response.raise_for_status()
    mount = response.json().get('secret/', {})
    if mount.get('type') != 'kv' or mount.get('options', {}).get('version') != '2':
        raise RuntimeError("secret/ must be an existing KV v2 mount")
    write_account_passwords(root_token, account_passwords)
    print("[Vault] Authentik account passwords seeded into KV v2.")


def seed_secrets(root_token):
    headers = {"X-Vault-Token": root_token}
    env = read_env()

    # Validate all new account credentials before performing any Vault writes.
    account_passwords = read_account_passwords()

    import secrets
    import uuid

    def get_vault_val(path, subkey):
        try:
            r = http_client.get(f"{VAULT_URL}/v1/secret/data/llm-stack/{path}", headers=headers, timeout=2)
            if r.status_code == 200:
                return r.json().get('data', {}).get('data', {}).get(subkey)
        except Exception:
            pass
        return None

    def sval(env_key, path, subkey, default_gen):
        v = env.get(env_key, '').strip()
        if v and 'change_me' not in v and not v.startswith('default_'):
            return v
        existing = get_vault_val(path, subkey)
        if existing:
            return existing
        return default_gen()

    # Enable KV v2 secret engine if not mounted
    r_mounts = http_client.get(f"{VAULT_URL}/v1/sys/mounts", headers=headers)
    mounts = r_mounts.json() if r_mounts.status_code == 200 else {}
    if 'secret/' not in mounts:
        print("[Vault] Mounting KV v2 secret engine at secret/...")
        http_client.post(f"{VAULT_URL}/v1/sys/mounts/secret", headers=headers, json={"type": "kv", "options": {"version": "2"}})

    # Authentik account passwords originate in setup.sh and must not be generated
    # independently here: the local bootstrap file and Vault must agree.
    write_account_passwords(root_token, account_passwords)

    # Write Postgres secret
    pg_pass = sval('POSTGRES_PASSWORD', 'postgres', 'POSTGRES_PASSWORD', lambda: secrets.token_hex(16))
    http_client.post(f"{VAULT_URL}/v1/secret/data/llm-stack/postgres", headers=headers, json={
        "data": {"POSTGRES_PASSWORD": pg_pass}
    })

    # Write ClickHouse secret
    ch_pass = sval('CLICKHOUSE_PASSWORD', 'clickhouse', 'CLICKHOUSE_PASSWORD', lambda: secrets.token_hex(16))
    http_client.post(f"{VAULT_URL}/v1/secret/data/llm-stack/clickhouse", headers=headers, json={
        "data": {"CLICKHOUSE_PASSWORD": ch_pass}
    })

    # Write Langfuse secrets
    http_client.post(f"{VAULT_URL}/v1/secret/data/llm-stack/langfuse", headers=headers, json={
        "data": {
            "SALT": sval('LANGFUSE_SALT', 'langfuse', 'SALT', lambda: secrets.token_hex(32)),
            "ENCRYPTION_KEY": sval('LANGFUSE_ENCRYPTION_KEY', 'langfuse', 'ENCRYPTION_KEY', lambda: secrets.token_hex(32)),
            "NEXTAUTH_SECRET": sval('LANGFUSE_NEXTAUTH_SECRET', 'langfuse', 'NEXTAUTH_SECRET', lambda: secrets.token_hex(32)),
            "INIT_PROJECT_PUBLIC_KEY": sval('LANGFUSE_INIT_PROJECT_PUBLIC_KEY', 'langfuse', 'INIT_PROJECT_PUBLIC_KEY', lambda: f"pk-lf-{uuid.uuid4()}"),
            "INIT_PROJECT_SECRET_KEY": sval('LANGFUSE_INIT_PROJECT_SECRET_KEY', 'langfuse', 'INIT_PROJECT_SECRET_KEY', lambda: f"sk-lf-{uuid.uuid4()}"),
            "OIDC_CLIENT_SECRET": env.get('LANGFUSE_OIDC_CLIENT_SECRET') or sval('LANGFUSE_OIDC_CLIENT_SECRET', 'langfuse', 'OIDC_CLIENT_SECRET', lambda: secrets.token_hex(32)),
            "INIT_USER_PASSWORD": sval('UI_PASSWORD', 'langfuse', 'INIT_USER_PASSWORD', lambda: env.get('UI_PASSWORD', ''))
        }
    })

    # Write SeaweedFS S3 credentials (admin identity + scoped Langfuse identity)
    s3_access = env.get('SEAWEEDFS_S3_ACCESS_KEY') or sval('SEAWEEDFS_S3_ACCESS_KEY', 'seaweedfs', 'S3_ACCESS_KEY', lambda: "seaweed_07efccd8f850")
    s3_secret = env.get('SEAWEEDFS_S3_SECRET_KEY') or sval('SEAWEEDFS_S3_SECRET_KEY', 'seaweedfs', 'S3_SECRET_KEY', lambda: "6344e975a9fc80ee7a07fe88a2add39c499fbe9fe007f7294cb3a8fbd1af586a")
    langfuse_s3_access = env.get('LANGFUSE_S3_ACCESS_KEY') or sval('LANGFUSE_S3_ACCESS_KEY', 'seaweedfs', 'LANGFUSE_S3_ACCESS_KEY', lambda: f"langfuse_{secrets.token_hex(6)}")
    langfuse_s3_secret = env.get('LANGFUSE_S3_SECRET_KEY') or sval('LANGFUSE_S3_SECRET_KEY', 'seaweedfs', 'LANGFUSE_S3_SECRET_KEY', lambda: secrets.token_hex(32))
    http_client.post(f"{VAULT_URL}/v1/secret/data/llm-stack/seaweedfs", headers=headers, json={
        "data": {
            "S3_ACCESS_KEY": s3_access,
            "S3_SECRET_KEY": s3_secret,
            "LANGFUSE_S3_ACCESS_KEY": langfuse_s3_access,
            "LANGFUSE_S3_SECRET_KEY": langfuse_s3_secret,
        }
    })

    # Write Redis auth
    redis_auth = sval('REDIS_AUTH', 'redis', 'AUTH', lambda: secrets.token_hex(24))
    http_client.post(f"{VAULT_URL}/v1/secret/data/llm-stack/redis", headers=headers, json={
        "data": {"AUTH": redis_auth}
    })

    # Write LiteLLM secrets
    litellm_master = sval('LITELLM_MASTER_KEY', 'litellm', 'MASTER_KEY', lambda: f"sk-{secrets.token_hex(24)}")
    ui_pass = sval('UI_PASSWORD', 'litellm', 'UI_PASSWORD', lambda: secrets.token_urlsafe(16))
    litellm_oidc = env.get('LITELLM_OIDC_CLIENT_SECRET') or sval('LITELLM_OIDC_CLIENT_SECRET', 'litellm', 'OIDC_CLIENT_SECRET', lambda: secrets.token_hex(32))
    http_client.post(f"{VAULT_URL}/v1/secret/data/llm-stack/litellm", headers=headers, json={
        "data": {
            "MASTER_KEY": litellm_master,
            "UI_PASSWORD": ui_pass,
            "OIDC_CLIENT_SECRET": litellm_oidc,
        }
    })

    # Write Open-WebUI secrets
    webui_secret = sval('WEBUI_SECRET_KEY', 'open-webui', 'WEBUI_SECRET_KEY', lambda: secrets.token_hex(32))
    qdrant_key = sval('QDRANT_API_KEY', 'open-webui', 'QDRANT_API_KEY', lambda: secrets.token_hex(32))
    http_client.post(f"{VAULT_URL}/v1/secret/data/llm-stack/open-webui", headers=headers, json={
        "data": {
            "WEBUI_SECRET_KEY": webui_secret,
            "QDRANT_API_KEY": qdrant_key,
        }
    })

    # Write Grafana secrets
    grafana_pass = sval('GRAFANA_ADMIN_PASSWORD', 'grafana', 'ADMIN_PASSWORD', lambda: secrets.token_hex(16))
    http_client.post(f"{VAULT_URL}/v1/secret/data/llm-stack/grafana", headers=headers, json={
        "data": {"ADMIN_PASSWORD": grafana_pass}
    })

    # Write Qdrant secrets
    http_client.post(f"{VAULT_URL}/v1/secret/data/llm-stack/qdrant", headers=headers, json={
        "data": {"API_KEY": qdrant_key}
    })

    # Write ClickHouse UI secrets
    chui_jwt = sval('CHOUSE_UI_JWT_SECRET', 'chouse-ui', 'JWT_SECRET', lambda: secrets.token_hex(32))
    chui_rbac_key = sval('CHOUSE_UI_RBAC_ENCRYPTION_KEY', 'chouse-ui', 'RBAC_ENCRYPTION_KEY', lambda: secrets.token_hex(32))
    chui_rbac_salt = sval('CHOUSE_UI_RBAC_ENCRYPTION_SALT', 'chouse-ui', 'RBAC_ENCRYPTION_SALT', lambda: secrets.token_hex(32))
    chui_oidc = env.get('CHOUSE_UI_OIDC_CLIENT_SECRET') or sval('CHOUSE_UI_OIDC_CLIENT_SECRET', 'chouse-ui', 'OIDC_CLIENT_SECRET', lambda: secrets.token_hex(32))
    http_client.post(f"{VAULT_URL}/v1/secret/data/llm-stack/chouse-ui", headers=headers, json={
        "data": {
            "JWT_SECRET": chui_jwt,
            "RBAC_ENCRYPTION_KEY": chui_rbac_key,
            "RBAC_ENCRYPTION_SALT": chui_rbac_salt,
            "OIDC_CLIENT_SECRET": chui_oidc,
        }
    })

    # Write SearXNG secret
    searx_secret = sval('SEARXNG_SECRET_KEY', 'searxng', 'SECRET_KEY', lambda: secrets.token_hex(32))
    http_client.post(f"{VAULT_URL}/v1/secret/data/llm-stack/searxng", headers=headers, json={
        "data": {"SECRET_KEY": searx_secret}
    })

    seeded_services = ["authentik", "postgres", "clickhouse", "langfuse", "seaweedfs", "redis", "litellm", "open-webui", "grafana", "qdrant", "chouse-ui", "searxng"]

    # Write Betterleaks secret
    betterleaks_key = sval('BETTERLEAKS_TOKEN_ENCRYPTION_KEY', 'betterleaks', 'TOKEN_ENCRYPTION_KEY', lambda: secrets.token_hex(32))
    http_client.post(f"{VAULT_URL}/v1/secret/data/llm-stack/betterleaks", headers=headers, json={
        "data": {
            "TOKEN_ENCRYPTION_KEY": betterleaks_key
        }
    })
    seeded_services.append("betterleaks")

    print(f"[Vault] Secrets seeded into KV v2 ({', '.join(seeded_services)}).")



def setup_oidc(root_token):
    headers = {"X-Vault-Token": root_token}
    env = read_env()
    domain = env.get('DOMAIN')
    if not domain:
        raise RuntimeError("DOMAIN must be set in .env for Vault OIDC configuration")
    client_secret = env.get('VAULT_OIDC_CLIENT_SECRET', '')

    # 1. Enable OIDC auth method if not enabled
    r_auth = http_client.get(f"{VAULT_URL}/v1/sys/auth", headers=headers)
    auth_methods = r_auth.json() if r_auth.status_code == 200 else {}
    if 'oidc/' not in auth_methods:
        print("[Vault] Enabling OIDC auth method at auth/oidc...")
        http_client.post(f"{VAULT_URL}/v1/sys/auth/oidc", headers=headers, json={"type": "oidc"})

    # 2. Get the CA chain Vault must trust to reach Authentik through Traefik (ingress CA:
    # the internal CA, or your own CA in custom mode; ACME modes use the system trust store).
    ca_pem = ""
    ca_paths = [
        "traefik/certs/ca.crt",
        "/etc/traefik/certs/ca.crt"
    ] if env.get('TLS_MODE', 'internal') in ('internal', 'custom') else []
    for p in ca_paths:
        if os.path.exists(p):
            try:
                with open(p) as f:
                    ca_pem = f.read()
                break
            except Exception:
                pass
    if env.get('TLS_MODE', 'internal') in ('internal', 'custom') and not ca_pem:
        raise RuntimeError(
            "internal and custom TLS require traefik/certs/ca.crt for OIDC discovery validation"
        )

    # 3. Configure OIDC method against Authentik
    print("[Vault] Configuring OIDC method against Authentik...")
    config_payload = {
        "oidc_discovery_url": f"https://authentik.{domain}/application/o/vault/",
        "bound_issuer": f"https://authentik.{domain}/application/o/vault/",
        "oidc_client_id": "vault",
        "oidc_client_secret": client_secret,
        "default_role": "admin"
    }
    if ca_pem:
        config_payload["oidc_discovery_ca_pem"] = ca_pem

    r_config = http_client.post(f"{VAULT_URL}/v1/auth/oidc/config", headers=headers, json=config_payload)
    if r_config.status_code not in (200, 204):
        raise RuntimeError(
            f"OIDC config failed ({r_config.status_code}): {r_config.text}"
        )

    # 4. Create 'admin' Vault Policy (full superuser capabilities across all paths & subpaths)
    admin_policy = 'path "*" {\n  capabilities = ["create", "read", "update", "delete", "list", "sudo"]\n}\npath "*/*" {\n  capabilities = ["create", "read", "update", "delete", "list", "sudo"]\n}\n'
    http_client.put(f"{VAULT_URL}/v1/sys/policy/admin", headers=headers, json={"policy": admin_policy})

    # 5. Create 'admin' OIDC Role
    print("[Vault] Creating 'admin' OIDC role...")
    redirect_uris = [
        f"https://vault.{domain}/ui/vault/auth/oidc/oidc/callback",
        f"http://localhost:8200/ui/vault/auth/oidc/oidc/callback",
        f"http://localhost:8201/ui/vault/auth/oidc/oidc/callback"
    ]
    http_client.post(f"{VAULT_URL}/v1/auth/oidc/role/admin", headers=headers, json={
        "user_claim": "email",
        "groups_claim": "groups",
        "allowed_redirect_uris": redirect_uris,
        "token_policies": ["admin"],
        "oidc_scopes": ["openid", "profile", "email", "groups"]
    })
    print("[Vault] OIDC auth method & admin role configured successfully!")


def load_root_token():
    if not os.path.exists(KEYS_FILE):
        raise RuntimeError(f"{KEYS_FILE} not found")
    with open(KEYS_FILE) as f:
        return json.load(f).get("root_token", "")


def main(argv=None):
    load_env_defaults()
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument(
        "--skip-oidc",
        action="store_true",
        help="Initialize, unseal, and seed Vault without configuring OIDC.",
    )
    modes.add_argument(
        "--oidc-only",
        action="store_true",
        help="Configure Vault OIDC using the existing root token.",
    )
    modes.add_argument(
        "--authentik-accounts-only",
        action="store_true",
        help="Update only Authentik account passwords in the existing KV v2 mount.",
    )
    modes.add_argument(
        "--check-ram",
        action="store_true",
        help="Fail unless rendered secrets are confined to private tmpfs.",
    )
    modes.add_argument(
        "--prepare-ram-link",
        action="store_true",
        help="Prepare only the per-instance repository symlink for RAM secrets.",
    )
    modes.add_argument(
        "--ensure-ram",
        action="store_true",
        help="Recreate the private tmpfs directory after reboot and validate it.",
    )
    args = parser.parse_args(argv)

    try:
        if args.prepare_ram_link:
            prepare_ram_link()
            return

        if args.ensure_ram:
            ensure_ram_directory()
            print("[Vault] Secret directory is private tmpfs.")
            return

        if args.check_ram:
            require_ram_directory()
            print("[Vault] Secret directory is private tmpfs.")
            return

        if args.oidc_only:
            root_token = load_root_token()
            if not root_token:
                raise RuntimeError("Vault root token is empty")
            setup_oidc(root_token)
            print("[Vault] OIDC provisioning completed successfully.")
            return

        if args.authentik_accounts_only:
            root_token = load_root_token()
            if not root_token:
                raise RuntimeError("Vault root token is empty")
            seed_authentik_accounts_only(root_token)
            print("[Vault] Authentik account provisioning completed successfully.")
            return

        root_token = init_and_unseal()
        seed_secrets(root_token)
        configure_agent_approle(root_token)
        if not args.skip_oidc:
            setup_oidc(root_token)
        print("[Vault] Provisioning completed successfully.")
    except Exception as e:
        print(f"[Vault] Error during provisioning: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
