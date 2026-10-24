# HashiCorp Vault — Enterprise Secrets Management & Encryption Vault

A centralized, encrypted secrets management vault integrated as a first-class service into `llm-stack`. Handles KV v2 secrets, dynamic secret rendering via Vault Agent into RAM-backed (`tmpfs`) environment files, and native Authentik OIDC SSO authentication.

---

## 🏗️ Architecture & Component Integration

| Component | Role | Configuration / Path |
| :--- | :--- | :--- |
| **`vault`** | Core vault server (`hashicorp/vault:2.0.4`, file storage engine on `/vault/data`). | [`config.hcl`](config.hcl), `127.0.0.1:8201:8200` (host port `8201` mapped to `:8200` to avoid conflict with native host Vault). |
| **`vault-agent`** | Sidecar using a scoped AppRole to render `.env` files into private `tmpfs`. | [`agent-config.hcl`](agent-config.hcl), [`templates/langfuse.env.tpl`](templates/langfuse.env.tpl) $\rightarrow$ `secrets_ram/langfuse.env`. |
| **`provision.sh`** | Automated init, unseal, secret seeding & OIDC setup. | [`provision.sh`](provision.sh), [`scripts/provision.py`](scripts/provision.py). |
| **Traefik** | Reverse proxy, domain routing & internal TLS termination. | `https://vault.${DOMAIN}` $\rightarrow$ `https://vault:8200` (via `vault-transport` serversTransport). |
| **Authentik** | Identity Provider (IdP) gating access via native OIDC. | [`authentik/blueprints/20-native-oidc.yaml`](../authentik/blueprints/20-native-oidc.yaml). |
| **Gatus** | Health monitoring. | Endpoint check `https://vault:8200/v1/sys/health` in [`gatus/config.yaml.template`](../gatus/config.yaml.template). |
| **Backup / Restore** | Stateful volume & key backup. | Volume `vault_data` and `.vault_keys.json` managed by [`../backup.sh`](../backup.sh) and [`../restore.sh`](../restore.sh). |

---

## 🔑 Key Subtleties & Architecture Decisions

### 1. Web UI & Docker Image Choice (`hashicorp/vault:2.0.4`)
* **Image**: Uses official `hashicorp/vault:2.0.4`.
* **Web UI**: Serves built-in Ember.js Web UI natively at `/ui/` (`https://vault.${DOMAIN}/ui/`).

### 2. OIDC Token Signing Algorithm (`RS256` vs `HS256`)
* **Symptom**: `id_token failed verification: unsupported signing algorithm, expected ["RS256"] got "HS256"`.
* **Subtlety**: Vault strictly requires OIDC ID Tokens to be signed using asymmetric RSA keys (**`RS256`**). Authentik's `OAuth2Provider` defaults to symmetric HMAC (`HS256`) unless explicitly configured with an RSA signing key.
* **Fix**: The Authentik blueprint [`authentik/blueprints/20-native-oidc.yaml`](../authentik/blueprints/20-native-oidc.yaml) explicitly binds Authentik's RSA key pair:
  ```yaml
  signing_key: !Find [authentik_crypto.certificatekeypair, [name, "authentik Self-signed Certificate"]]
  ```

### 3. TLS Certificate Verification for Internal OIDC Discovery (`oidc_discovery_ca_pem`)
* **Symptom**: `Config Status: 400 error checking oidc discovery URL`.
* **Subtlety**: When Vault queries Authentik's OpenID Discovery endpoint (`https://authentik.${DOMAIN}/application/o/vault/`), Vault executes an internal HTTPS request from inside the container. In `TLS_MODE=internal` or `custom`, Vault's internal Go HTTP client rejects the ingress certificate unless its CA chain is explicitly supplied as a trust anchor. Vault's own listener uses a separate certificate from the internal CA (`traefik/certs/vault.crt`).
* **Fix**: [`setup.sh`](../setup.sh) writes the ingress CA chain to `traefik/certs/ca.crt` (the internal CA, or your own CA in `TLS_MODE=custom`), and [`vault/scripts/provision.py`](scripts/provision.py) passes it into Vault's OIDC configuration via `oidc_discovery_ca_pem`. Provisioning fails closed if the certificate is missing or Vault rejects the discovery configuration:
  ```python
  config_payload = {
      "oidc_discovery_url": f"https://authentik.{domain}/application/o/vault/",
      "oidc_client_id": "vault",
      "oidc_client_secret": client_secret,
      "default_role": "admin",
      "oidc_discovery_ca_pem": ca_pem
  }
  ```

### 4. Root Policy Restriction & Web UI ACL Wildcard (`Resultant ACL check failed`)
* **Symptom 1**: `Vault login failed: auth methods cannot create root tokens`.
* **Subtlety 1**: Vault's security model strictly prohibits dynamic Auth Methods (OIDC, Userpass, AppRole) from generating tokens attached to the built-in `root` policy (`token_policies: ["root"]`).
* **Symptom 2**: `Resultant ACL check failed. Links might be shown that you don't have access to.` in the Vault Web UI navigation sidebar.
* **Subtlety 2**: In Vault HCL ACL policies, `path "*"` only matches single-segment root paths. Nested subpaths queried by the Web UI (such as `sys/capabilities-self`, `sys/internal/ui/mounts`, `secret/data/...`) require a recursive wildcard (`path "*/*"`).
* **Fix**: [`vault/scripts/provision.py`](scripts/provision.py) creates a dedicated Vault policy named **`admin`** with both root and subpath wildcards granting full superuser capabilities, and binds the OIDC role to `token_policies: ["admin"]`:
  ```hcl
  path "*" {
    capabilities = ["create", "read", "update", "delete", "list", "sudo"]
  }
  path "*/*" {
    capabilities = ["create", "read", "update", "delete", "list", "sudo"]
  }
  ```

### 5. Host Port Mapping & Host Conflict Prevention (`127.0.0.1:8201:8200`)
* **Subtlety**: A native system `vault.service` may be running on the host listening on `127.0.0.1:8200`.
* **Fix**: The container maps host port `8201` to internal container port `8200` (`127.0.0.1:8201:8200`), leaving internal Docker network traffic on standard port `8200` (`http://vault:8200`) completely intact.

---

## 🔒 Authentication & Secrets

### Root Token & Unseal Keys (`.vault_keys.json`)
During initial stack bootstrapping (`./setup.sh` $\rightarrow$ `vault/provision.sh`), Vault is initialized and unsealed via Shamir key sharing.
* The unseal key and **Root Token** are saved in `.vault_keys.json` at the repository root.
* `.vault_keys.json` is protected with `chmod 600` permissions and ignored by Git.

### Logging in to the Web UI (`https://vault.${DOMAIN}`)

1. **Option A: OIDC SSO (Recommended)**
   * Select **OIDC** in the Method dropdown on `https://vault.${DOMAIN}`.
   * Click **Sign in with OIDC Provider** (role defaults to `admin`).
   * Authenticate via Authentik SSO.

2. **Option B: Token (Emergency Root)**
   * Select **Token** in the Method dropdown.
   * Enter the `root_token` from `.vault_keys.json`.

---

## 🚀 Developer Onboarding & Automated Unseal Workflow

When a new developer clones the repository or provisions a fresh environment, **zero manual unseal or key typing is required**. The entire lifecycle is managed programmatically via code.

### 1. Fresh Clone & First-Time Provisioning
Run `./setup.sh` to generate the environment and templates, then `./start.sh` to execute the following automated sequence:
1. **Container Startup**: `docker compose up -d vault` boots the `hashicorp/vault:2.0.4` container.
2. **Initialization (`/v1/sys/init`)**: `vault/scripts/provision.py` checks if Vault is initialized. If not, it requests initial Shamir key shares (`secret_shares: 1, secret_threshold: 1`).
3. **Key Persistence (`.vault_keys.json`)**: The unseal key and `root_token` are written to `.vault_keys.json` with `chmod 600` permissions (`.gitignore`d).
4. **Automated Unseal (`/v1/sys/unseal`)**: The unseal key is sent via REST API to unseal the storage barrier.
5. **Secrets Seeding (`secret/data/llm-stack/*`)**: KV v2 secret engine is mounted and all 14 applicative secrets are seeded into Vault.
6. **Vault Agent AppRole**: Provisioning writes a read-only KV v2 policy and private AppRole credentials to `vault/secrets_ram/.agent-role-id` and `.agent-secret-id`. The root token is never given to the Agent.
7. **Sidecar Rendering**: `setup.sh` creates only a repository symlink to a per-instance private directory under `/dev/shm`; `start.sh` recreates the target after reboot and rejects wrong links, owners, permissions, or filesystems before starting Vault. `vault-agent` renders into that RAM directory (`/run/secrets/*.env` / `vault/secrets_ram/*.env`).
8. **Stack Boot**: Downstream services consume only their own environment file. SeaweedFS and the Authentik one-shot job mount only the specific files they need; the full Agent credential directory is not mounted into applications. The Agent's render group matches the pinned SeaweedFS process group so the S3 file remains `0640` rather than world-readable.

This AppRole and private `tmpfs` layout is an isolated UAT candidate. An existing nonempty disk-backed secret directory is never replaced automatically. Do not apply the candidate to production until a separate CAB approves migration of that directory, legacy token handling, service recreation, and rollback. `.env` and `.vault_keys.json` remain persistent under the current bootstrap design.

The explicit, fail-closed legacy migration tool, UAT rehearsal, quarantine
behavior, and production hold points are documented in
[`MIGRATION.md`](MIGRATION.md). A successful fresh-install UAT alone does not
validate migration of an existing installation.

### 2. Resealed Vault Recovery (Host Reboot or Container Restart)
If Vault becomes sealed (for instance, after a host reboot or container restart):
```bash
bash vault/provision.sh
```
`vault/provision.sh` checks `/v1/sys/health`, reads the saved key from `.vault_keys.json`, calls `/v1/sys/unseal`, and re-triggers `vault-agent` rendering. No manual Shamir key entry is ever needed.

### 3. Targeted Authentik account migration on an existing deployment

After validating the exact candidate in disposable UAT, use the two narrow modes below
instead of `./start.sh` or full `vault/provision.sh`. The first command requires an
existing `.env`, backs it up with mode `0600`, and adds only missing Alice/Bob passwords;
it never regenerates existing secrets, hydrates templates, or starts containers. The
second command requires an existing Vault root token and KV v2 mount, then writes only
`secret/data/llm-stack/authentik`. Neither command prints password values.

```bash
./setup.sh --authentik-accounts-only
python3 vault/scripts/provision.py --authentik-accounts-only
```

The Vault Agent must then be recreated by itself to load the new account template.
After its health check succeeds, regenerate the `01-users-groups` blueprint from its
template using the existing environment and rerun only the Authentik one-shot
provisioning service. Do not use `./start.sh` for this live migration: it invokes
`docker compose up -d` for the entire stack, including LiteLLM. Full
`vault/provision.sh` also rewrites other applications' KV entries, including LiteLLM.
Record the production LiteLLM container ID and start time before and after the
migration, inspect Vault Agent and Authentik logs, and verify Alice/Bob sign-in and
the full smoke suite. Preserve the `.env` backup until the rollout is accepted.

### 4. Summary of Onboarding Commands

| Scenario | Command | Expected Outcome |
| :--- | :--- | :--- |
| **New developer setup** | `./setup.sh` then `./start.sh` | Generates configuration, then initializes Vault, seeds secrets, renders RAM env files, and starts the stack. |
| **Re-unseal after reboot** | `bash vault/provision.sh` | Reads `.vault_keys.json`, unseals Vault via API, re-renders secrets. |
| **Manual UI login** | `https://vault.${DOMAIN}` | Click **Sign in with OIDC Provider** (Authentik SSO) or use Token from `.vault_keys.json`. |

---

## 🗄️ Application Secrets Catalog & Dynamic Provisioning

All application secrets are dynamically managed and stored in Vault's KV v2 secrets engine under the mount `secret/` at path `secret/data/llm-stack/<service>`.

### 1. Secret Seeding Mechanism (`vault/scripts/provision.py`)
During stack bootstrap (`./setup.sh` $\rightarrow$ `vault/provision.sh` $\rightarrow$ `vault/scripts/provision.py`), secrets are seeded idempotently using the `sval()` helper:
1. **Preservation**: If the secret already exists in Vault KV v2, the existing value is preserved.
2. **Environment Fallback**: If missing in Vault, it checks for an existing value in `.env` (migration path).
3. **Cryptographic Generation**: If neither exists, a high-entropy secret is generated automatically using Python's `secrets` module (`secrets.token_hex(...)`).

### 2. KV v2 Application Secrets Catalog

| Service Path | Secret Keys | Purpose & Generator |
| :--- | :--- | :--- |
| `secret/data/llm-stack/authentik` | `SECRET_KEY`, `POSTGRES_PASSWORD`, `AUTHENTIK_ADMIN_PASSWORD`, `ALICE_PASSWORD`, `BOB_PASSWORD` | Django secret key, DB password, admin & test account credentials. |
| `secret/data/llm-stack/postgres` | `POSTGRES_PASSWORD` | PostgreSQL superuser password (`openssl rand -hex 24`). |
| `secret/data/llm-stack/clickhouse` | `CLICKHOUSE_PASSWORD` | ClickHouse admin password. |
| `secret/data/llm-stack/redis` | `REDIS_PASSWORD` | Redis cache auth password. |
| `secret/data/llm-stack/litellm` | `MASTER_KEY`, `SALT_KEY` | LiteLLM admin API key (`sk-...`) and encryption salt. |
| `secret/data/llm-stack/langfuse` | `NEXTAUTH_SECRET`, `SALT`, `ENCRYPTION_KEY`, `INIT_PROJECT_PUBLIC_KEY`, `INIT_PROJECT_SECRET_KEY` | NextAuth session secrets and project API keys. |
| `secret/data/llm-stack/seaweedfs` | `ADMIN_ACCESS_KEY`, `ADMIN_SECRET_KEY`, `READONLY_ACCESS_KEY`, `READONLY_SECRET_KEY` | SeaweedFS S3 SigV4 credentials. |
| `secret/data/llm-stack/open-webui` | `WEBUI_SECRET_KEY` | Open-WebUI JWT signing secret. |
| `secret/data/llm-stack/grafana` | `ADMIN_PASSWORD`, `SECRET_KEY` | Grafana admin credentials and encryption key. |
| `secret/data/llm-stack/qdrant` | `API_KEY` | Qdrant vector database API key. |
| `secret/data/llm-stack/chouse-ui` | `OIDC_CLIENT_SECRET` | ClickHouse UI Authentik OIDC client secret. |
| `secret/data/llm-stack/searxng` | `SECRET_KEY` | SearXNG session encryption key. |
| `secret/data/llm-stack/betterleaks` | `TOKEN_ENCRYPTION_KEY` | Betterleaks AES-256-GCM key for reversible vaulted tokenization. |

### 3. Template Projection & RAM Tmpfs (`vault-agent`)
`vault-agent` runs as a sidecar with a dedicated AppRole (`secret/data/llm-stack/*` read-only policy). It evaluates Consul Template files in `vault/templates/*.tpl` and renders them into memory-backed tmpfs (`vault/secrets_ram/*.env`).
- For example, `vault/templates/betterleaks.env.tpl` extracts `TOKEN_ENCRYPTION_KEY` from `secret/data/llm-stack/betterleaks` and renders `TOKEN_ENCRYPTION_KEY=...` into `vault/secrets_ram/betterleaks.env`.
- Containers mount their specific `.env` file via `env_file:` in `docker-compose.yml`. Secrets never touch persistent disk.

### 4. Reading & Rotating Secrets via Vault CLI

To inspect secrets in Vault:
```bash
# Read Betterleaks secrets
docker compose exec -T vault vault kv get secret/llm-stack/betterleaks

# Read a specific field (e.g. TOKEN_ENCRYPTION_KEY)
docker compose exec -T vault vault kv get -field=TOKEN_ENCRYPTION_KEY secret/llm-stack/betterleaks
```

To rotate a secret:
```bash
# 1. Update the secret in Vault KV v2
docker compose exec -T vault vault kv patch secret/llm-stack/betterleaks TOKEN_ENCRYPTION_KEY="$(openssl rand -hex 32)"

# 2. Trigger Vault Agent to re-render templates into tmpfs
docker compose restart vault-agent

# 3. Reload downstream service configuration
docker compose restart betterleaks
```

---

## 🧪 Functional Verification

To run end-to-end smoke testing on Vault:
```bash
./smoke_test.sh VAULT
```
Verifies Vault readiness, unseal status, KV v2 secret read/write capability, and Web UI availability.
