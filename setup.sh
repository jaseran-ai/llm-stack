#!/usr/bin/env bash
# ==============================================================================
# LLM Stack Setup & Environment Hydrator
# 100% As-Code Reproducibility — Secret Generation & Domain Hydration
# ==============================================================================

set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

EMAIL_DOMAIN="${EMAIL_DOMAIN:-example.com}"

show_help() {
    cat <<EOF
========================================================================
 LLM Stack Setup & Environment Hydrator
========================================================================
Usage: ./setup.sh [OPTIONS]

Options:
  --domain=DOMAIN         Explicitly set the host domain (e.g. example.com or mymachine.local).
                          Overrides auto-detection (mDNS/Avahi or LAN IP).
  --dns-mode=MODE         DNS resolution mode: hosts (default), coredns, or cloudflare.
                          hosts:      Zero-dependency /etc/hosts snippet or existing network DNS.
                          coredns:    Bundles local CoreDNS server resolving *.DOMAIN to LAN IP.
                          cloudflare: Cloudflare Zero Trust Tunnel (COMPOSE_PROFILES=cloudflare).
  --force-regen           Regenerate all cryptographic secrets in .env without interactive prompt.
                          CAUTION: Breaks auth for existing Docker volumes unless recreated!
  --authentik-accounts-only
                          Add missing Alice/Bob passwords to an existing .env only.
                          Does not hydrate templates or start containers.
  --enable-cloudflared    Activate optional Cloudflare Tunnel profile (alias for --dns-mode=cloudflare).
  -h, --help              Show this help message and exit.

Examples:
  ./setup.sh
  ./setup.sh --domain=example.com
  ./setup.sh --dns-mode=coredns
  ./setup.sh --dns-mode=cloudflare
  ./setup.sh --force-regen
  ./setup.sh --authentik-accounts-only
  ./setup.sh --enable-cloudflared
========================================================================
EOF
    exit 0
}

# Detect flags
FORCE_REGEN=false
AUTHENTIK_ACCOUNTS_ONLY=false
DOMAIN_OVERRIDE=""
DNS_MODE_OVERRIDE=""
for arg in "$@"; do
    case "$arg" in
        -h|--help)
            show_help
            ;;
        --force-regen)
            FORCE_REGEN=true
            ;;
        --authentik-accounts-only)
            AUTHENTIK_ACCOUNTS_ONLY=true
            ;;
        --domain=*)
            DOMAIN_OVERRIDE="${arg#--domain=}"
            ;;
        --dns-mode=*)
            DNS_MODE_OVERRIDE="${arg#--dns-mode=}"
            ;;
        --enable-cloudflared)
            DNS_MODE_OVERRIDE="cloudflare"
            ;;
    esac
done

# Automatic detection of the local domain, without ever depending on a name hardcoded for a
# specific machine. Priority order:
#   1. --domain=xxx (CLI flag) or the DOMAIN environment variable (explicit override)
#   2. If avahi-daemon is running: "$(hostname).local" (the mDNS name actually published on the LAN)
#   3. Otherwise: the detected LAN IP, formatted as a hostname ("192-168-1-100.local")
#   4. Last resort (nothing detected): "llm-stack.local"
#
# IMPORTANT: mDNS/Avahi ONLY publishes the exact name "<hostname>.local", never wildcard
# subdomains. This project routes by subdomain (chat.${DOMAIN}, grafana.${DOMAIN}, etc. via
# Traefik): whatever DOMAIN ends up being, these subdomains will NEVER resolve automatically
# through Avahi alone. An /etc/hosts entry (or a local DNS server with a wildcard record) is
# still required for each subdomain — the script prints a ready-to-use snippet at the end.
detect_lan_ip() {
    local ip
    ip="$(ip route get 1.1.1.1 2>/dev/null | awk '{print $7; exit}')"
    if [ -z "$ip" ]; then
        ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
    fi
    echo "$ip"
}

detect_domain() {
    if command -v avahi-daemon >/dev/null 2>&1 && \
       { systemctl is-active --quiet avahi-daemon 2>/dev/null || pgrep -x avahi-daemon >/dev/null 2>&1; }; then
        echo "$(hostname).local"
        return
    fi

    local ip
    ip="$(detect_lan_ip)"
    if [ -n "$ip" ]; then
        echo "${ip//./-}.local"
        return
    fi

    echo "llm-stack.local"
}

LAN_IP="$(detect_lan_ip)"
[ -z "$LAN_IP" ] && LAN_IP="127.0.0.1"

if [ -n "$DOMAIN_OVERRIDE" ]; then
    DOMAIN="$DOMAIN_OVERRIDE"
elif [ -n "${DOMAIN:-}" ]; then
    : # DOMAIN was already set in the environment, use it as-is
else
    DOMAIN="$(detect_domain)"
fi

if [ -n "$DNS_MODE_OVERRIDE" ]; then
    case "$DNS_MODE_OVERRIDE" in
        hosts|coredns|cloudflare)
            DNS_MODE="$DNS_MODE_OVERRIDE"
            ;;
        *)
            echo "ERROR: Invalid --dns-mode '$DNS_MODE_OVERRIDE'. Must be one of: hosts, coredns, cloudflare." >&2
            exit 1
            ;;
    esac
elif [ -f .env ] && grep -q '^DNS_MODE=' .env; then
    DNS_MODE="$(grep -m1 '^DNS_MODE=' .env | cut -d= -f2 | tr -d '"'\'' ')"
elif [ -f .env ] && grep -q '^COMPOSE_PROFILES=.*cloudflared' .env; then
    DNS_MODE="cloudflare"
elif [ -n "${DNS_MODE:-}" ]; then
    : # Keep environment variable
else
    DNS_MODE="hosts"
fi

if [ -f .env ] && grep -q '^COREDNS_BIND_IP=' .env; then
    COREDNS_BIND_IP="$(grep -m1 '^COREDNS_BIND_IP=' .env | cut -d= -f2 | tr -d '"'\'' ')"
fi
[ -z "${COREDNS_BIND_IP:-}" ] && COREDNS_BIND_IP="$LAN_IP"

case "$DNS_MODE" in
    cloudflare)
        COMPOSE_PROFILES="cloudflare"
        ;;
    coredns)
        COMPOSE_PROFILES="coredns"
        ;;
    hosts|*)
        COMPOSE_PROFILES=""
        ;;
esac

echo "========================================================================"
echo " Setting up the LLM Stack (As-Code & Security Hydration)"
echo "========================================================================"
echo "Detected domain: ${DOMAIN}"
echo "DNS resolution mode: ${DNS_MODE}"

# 1. Check system dependencies
command -v docker >/dev/null 2>&1 || { echo "Docker is required but not installed."; exit 1; }
command -v openssl >/dev/null 2>&1 || { echo "OpenSSL is required but not installed."; exit 1; }

# Back up the previous .env before any regeneration (precaution, allows rolling back)
backup_env() {
    local backup_file
    backup_file=".env.bak.$(date +%s)"
    cp .env "$backup_file"
    chmod 600 "$backup_file"
    echo "Previous .env backed up as ${backup_file}"
}

# Maps a dynamically-generated secret's variable name to the shell command that produces a
# fresh value for it. The single source of truth for "how is X generated" - both
# generate_env() (a brand new .env) and add_missing_secrets() (an existing .env, only filling
# in whatever a newer version of this script now expects that isn't there yet) call this, so
# the two paths can never drift out of sync with each other. To add a secret for a new service
# (see ADDING_AN_APPLICATION.md), add one case here and its name to GENERATED_SECRET_NAMES
# below - nothing else needs to change for both a fresh install and an existing deployment to
# pick it up correctly.
generate_secret_value() {
    case "$1" in
        SEAWEEDFS_S3_ACCESS_KEY) echo "seaweed_$(openssl rand -hex 6)" ;;
        SEAWEEDFS_S3_SECRET_KEY) openssl rand -hex 32 ;;
        LANGFUSE_OIDC_CLIENT_SECRET) openssl rand -hex 32 ;;
        LITELLM_OIDC_CLIENT_SECRET) openssl rand -hex 32 ;;
        CHOUSE_UI_OIDC_CLIENT_SECRET) openssl rand -hex 32 ;;
        VAULT_OIDC_CLIENT_SECRET) openssl rand -hex 32 ;;
        CHOUSE_UI_JWT_SECRET) openssl rand -hex 32 ;;
        CHOUSE_UI_RBAC_ENCRYPTION_KEY) openssl rand -hex 32 ;;
        CHOUSE_UI_RBAC_ENCRYPTION_SALT) openssl rand -hex 32 ;;
        POSTGRES_PASSWORD) openssl rand -hex 24 ;;
        CLICKHOUSE_PASSWORD) openssl rand -hex 24 ;;
        GRAFANA_ADMIN_PASSWORD) openssl rand -hex 16 ;;
        QDRANT_API_KEY) openssl rand -hex 24 ;;
        LANGFUSE_SALT) openssl rand -hex 16 ;;
        LANGFUSE_ENCRYPTION_KEY) openssl rand -hex 32 ;;
        LANGFUSE_NEXTAUTH_SECRET) openssl rand -hex 32 ;;
        LITELLM_MASTER_KEY) echo "sk-$(openssl rand -hex 24)" ;;
        WEBUI_SECRET_KEY) openssl rand -hex 32 ;;
        REDIS_AUTH) openssl rand -hex 24 ;;
        LANGFUSE_INIT_PROJECT_PUBLIC_KEY) echo "pk-lf-$(python3 -c 'import uuid; print(uuid.uuid4())')" ;;
        LANGFUSE_INIT_PROJECT_SECRET_KEY) echo "sk-lf-$(python3 -c 'import uuid; print(uuid.uuid4())')" ;;
        SEARXNG_SECRET_KEY) openssl rand -hex 32 ;;
        AUTHENTIK_SECRET_KEY) openssl rand -base64 60 | tr -d '\n' ;;
        AUTHENTIK_BOOTSTRAP_TOKEN) openssl rand -hex 32 ;;
        UI_PASSWORD) openssl rand -hex 16 ;;
        ALICE_PASSWORD|BOB_PASSWORD) openssl rand -hex 32 ;;
        BACKUP_PASSPHRASE) openssl rand -hex 32 ;;
        BETTERLEAKS_TOKEN_ENCRYPTION_KEY) openssl rand -hex 32 ;;
        SECRETS_RAM_UID) if [ -f .env ]; then stat -c %u .env; else id -u; fi ;;
        SECRETS_RAM_GID) if [ -f .env ]; then stat -c %g .env; else id -g; fi ;;
        SECRETS_RENDER_GID) echo 1000 ;;
        SECRETS_RAM_ID) printf '%s\n' "${SECRETS_RAM_ID:-$(openssl rand -hex 8)}" ;;
        CLOUDFLARE_TUNNEL_TOKEN) echo "${CLOUDFLARE_TUNNEL_TOKEN:-}" ;;
        *) echo "" ;;
    esac
}

GENERATED_SECRET_NAMES=(
    LANGFUSE_OIDC_CLIENT_SECRET LITELLM_OIDC_CLIENT_SECRET CHOUSE_UI_OIDC_CLIENT_SECRET VAULT_OIDC_CLIENT_SECRET
    POSTGRES_PASSWORD CLICKHOUSE_PASSWORD AUTHENTIK_SECRET_KEY AUTHENTIK_BOOTSTRAP_TOKEN UI_PASSWORD
    ALICE_PASSWORD BOB_PASSWORD
    BACKUP_PASSPHRASE
    SECRETS_RAM_UID SECRETS_RAM_GID SECRETS_RENDER_GID
    SECRETS_RAM_ID
    CLOUDFLARE_TUNNEL_TOKEN
)

if [[ -n "${SECRETS_RAM_ID:-}" && ! "${SECRETS_RAM_ID}" =~ ^[0-9a-f]{16}$ ]]; then
    echo "ERROR: SECRETS_RAM_ID must be a generated 16-character hex ID." >&2
    exit 1
fi

# Generate unique cryptographic secrets and write the .env file
generate_env() {
    echo "Generating the .env file and unique cryptographic secrets..."

    for name in "${GENERATED_SECRET_NAMES[@]}"; do
        printf -v "$name" '%s' "$(generate_secret_value "$name")"
    done

    # The loop above assigns these generated values through printf -v.
    # shellcheck disable=SC2153
    cat <<EOF > .env
# ==============================================================================
# LLM Stack Environment Configuration (.env)
# ==============================================================================

# --- Ports ---
OLLAMA_WEBAPI_PORT=12434
OPEN_WEBUI_PORT=8080
LITELLM_PORT=4001

# --- Dynamic Host Domain & Email Domain ---
DOMAIN=${DOMAIN}
EMAIL_DOMAIN=${EMAIL_DOMAIN}
SECRETS_RAM_UID=${SECRETS_RAM_UID}
SECRETS_RAM_GID=${SECRETS_RAM_GID}
SECRETS_RENDER_GID=${SECRETS_RENDER_GID}
SECRETS_RAM_ID=${SECRETS_RAM_ID}

# --- TLS & Ingress Configuration ---
TLS_MODE=${TLS_MODE:-internal}
CLOUDFLARE_API_TOKEN=${CLOUDFLARE_API_TOKEN:-}
ACME_EMAIL=${ACME_EMAIL:-}

# --- DNS & Resolution Mode (hosts | coredns | cloudflare) ---
DNS_MODE=${DNS_MODE}
COREDNS_BIND_IP=${COREDNS_BIND_IP}

# --- Optional Profiles ---
COMPOSE_PROFILES=${COMPOSE_PROFILES}
CLOUDFLARE_TUNNEL_TOKEN=${CLOUDFLARE_TUNNEL_TOKEN:-}

# --- Bootstrap & IdP Secrets ---
# Required in .env for database bootstrap and Authentik/Vault OIDC discovery setup
POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
CLICKHOUSE_PASSWORD=${CLICKHOUSE_PASSWORD}
AUTHENTIK_SECRET_KEY=${AUTHENTIK_SECRET_KEY}
AUTHENTIK_BOOTSTRAP_TOKEN=${AUTHENTIK_BOOTSTRAP_TOKEN}
VAULT_OIDC_CLIENT_SECRET=${VAULT_OIDC_CLIENT_SECRET}
LANGFUSE_OIDC_CLIENT_SECRET=${LANGFUSE_OIDC_CLIENT_SECRET}
LITELLM_OIDC_CLIENT_SECRET=${LITELLM_OIDC_CLIENT_SECRET}
CHOUSE_UI_OIDC_CLIENT_SECRET=${CHOUSE_UI_OIDC_CLIENT_SECRET}
UI_PASSWORD=${UI_PASSWORD}
ALICE_PASSWORD=${ALICE_PASSWORD}
BOB_PASSWORD=${BOB_PASSWORD}
BACKUP_PASSPHRASE=${BACKUP_PASSPHRASE}

# Langfuse / ClickHouse / Redis Operational Configuration (non-secret, explicit to avoid any implicit fallback in docker-compose.yml)
TELEMETRY_ENABLED=true
LANGFUSE_ENABLE_EXPERIMENTAL_FEATURES=true
LANGFUSE_USE_AZURE_BLOB=false
LANGFUSE_INIT_ORG_ID=cmct8rhde0006lm078h7kb93c
LANGFUSE_INIT_ORG_NAME="LLMStack"
LANGFUSE_INIT_PROJECT_ID=cmct8ruwk000blm07y026jjpp
LANGFUSE_INIT_PROJECT_NAME="llm-stack-project"

CLICKHOUSE_URL=http://clickhouse:8123
CLICKHOUSE_USER=clickhouse
CLICKHOUSE_CLUSTER_ENABLED=false

REDIS_HOST=redis
REDIS_PORT=6379
REDIS_TLS_ENABLED=false
REDIS_TLS_CA=/certs/ca.crt
REDIS_TLS_CERT=/certs/redis.crt
REDIS_TLS_KEY=/certs/redis.key

# Langfuse S3 Storage Buckets (SeaweedFS backend)
LANGFUSE_S3_EVENT_UPLOAD_BUCKET=langfuse
LANGFUSE_S3_EVENT_UPLOAD_REGION=auto
LANGFUSE_S3_EVENT_UPLOAD_ENDPOINT=http://seaweedfs:8333
LANGFUSE_S3_EVENT_UPLOAD_FORCE_PATH_STYLE=true
LANGFUSE_S3_EVENT_UPLOAD_PREFIX=events/
LANGFUSE_S3_MEDIA_UPLOAD_BUCKET=langfuse
LANGFUSE_S3_MEDIA_UPLOAD_REGION=auto
LANGFUSE_S3_MEDIA_UPLOAD_ENDPOINT=http://seaweedfs:8333
LANGFUSE_S3_MEDIA_UPLOAD_FORCE_PATH_STYLE=true
LANGFUSE_S3_MEDIA_UPLOAD_PREFIX=media/
LANGFUSE_S3_BATCH_EXPORT_ENABLED=false
LANGFUSE_S3_BATCH_EXPORT_BUCKET=langfuse
LANGFUSE_S3_BATCH_EXPORT_PREFIX=exports/
LANGFUSE_S3_BATCH_EXPORT_REGION=auto
LANGFUSE_S3_BATCH_EXPORT_ENDPOINT=http://seaweedfs:8333
LANGFUSE_S3_BATCH_EXPORT_EXTERNAL_ENDPOINT=https://s3.${DOMAIN}
LANGFUSE_S3_BATCH_EXPORT_FORCE_PATH_STYLE=true
EOF
    add_missing_secrets
    echo ".env file generated successfully!"
}

add_missing_secrets() {
    local names=("$@")
    local added=()
    local secret_names_to_add=()
    local dns_settings_to_add=()
    local name value
    local specific_subset=true
    if [ "${#names[@]}" -eq 0 ]; then
        names=("${GENERATED_SECRET_NAMES[@]}")
        specific_subset=false
    fi
    for name in "${names[@]}"; do
        if ! grep -q "^${name}=" .env; then
            secret_names_to_add+=("$name")
            added+=("$name")
        fi
    done
    if [ "$specific_subset" = false ]; then
        if ! grep -q "^DNS_MODE=" .env; then
            dns_settings_to_add+=("DNS_MODE=${DNS_MODE}")
            added+=("DNS_MODE")
        fi
        if ! grep -q "^COREDNS_BIND_IP=" .env; then
            dns_settings_to_add+=("COREDNS_BIND_IP=${COREDNS_BIND_IP}")
            added+=("COREDNS_BIND_IP")
        fi
        if ! grep -q "^COMPOSE_PROFILES=" .env; then
            dns_settings_to_add+=("COMPOSE_PROFILES=${COMPOSE_PROFILES}")
            added+=("COMPOSE_PROFILES")
        fi
    fi
    if [ "${#added[@]}" -eq 0 ]; then
        if [ -n "$DNS_MODE_OVERRIDE" ] && [ "$specific_subset" = false ]; then
            sed -i "s/^DNS_MODE=.*/DNS_MODE=${DNS_MODE}/" .env
            sed -i "s/^COMPOSE_PROFILES=.*/COMPOSE_PROFILES=${COMPOSE_PROFILES}/" .env
        fi
        echo "No new secrets to add - the existing .env already has everything this version of setup.sh expects."
        return
    fi
    backup_env
    for setting in "${dns_settings_to_add[@]}"; do
        echo "$setting" >> .env
    done
    if [ -n "$DNS_MODE_OVERRIDE" ] && [ "$specific_subset" = false ]; then
        sed -i "s/^DNS_MODE=.*/DNS_MODE=${DNS_MODE}/" .env
        sed -i "s/^COMPOSE_PROFILES=.*/COMPOSE_PROFILES=${COMPOSE_PROFILES}/" .env
    fi
    for name in "${secret_names_to_add[@]}"; do
        value="$(generate_secret_value "$name")"
        echo "${name}=${value}" >> .env
    done
    echo "Added ${#added[@]} newly-required setting(s)/secret(s) to the existing .env: ${added[*]}"
}

if [ "$AUTHENTIK_ACCOUNTS_ONLY" = true ]; then
    if [ "$FORCE_REGEN" = true ]; then
        echo "ERROR: --authentik-accounts-only cannot be combined with --force-regen." >&2
        exit 1
    fi
    if [ ! -f .env ]; then
        echo "ERROR: --authentik-accounts-only requires an existing .env." >&2
        exit 1
    fi
    chmod 600 .env
    for name in ALICE_PASSWORD BOB_PASSWORD; do
        if grep -q "^${name}=" .env; then
            value="$(grep -m1 "^${name}=" .env | cut -d= -f2-)"
            if [ -z "$value" ] || [[ "${value,,}" == *change_me* ]]; then
                echo "ERROR: ${name} is empty or a placeholder; refusing partial migration." >&2
                exit 1
            fi
        fi
    done
    add_missing_secrets ALICE_PASSWORD BOB_PASSWORD
    echo "Authentik account secrets are present in .env; no templates or containers were changed."
    exit 0
fi

# 2. Decide what to do about .env: generate, keep, or regenerate with confirmation
if [ ! -f .env ]; then
    generate_env
elif [ "$FORCE_REGEN" = true ]; then
    echo "--force-regen is set: regenerating .env without interactive confirmation."
    backup_env
    generate_env
elif [ -t 0 ]; then
    echo "A .env file already exists."
    echo "WARNING: if the stack has already been started, the passwords (PostgreSQL, ClickHouse,"
    echo "   Qdrant, etc.) are already baked into the existing Docker volumes. Regenerating .env"
    echo "   WITHOUT recreating those volumes will break authentication for every dependent service"
    echo "   (Langfuse, LiteLLM, Authentik, ClickHouse...)."
    echo "   Recommended before continuing: 'docker compose down' (or even remove the affected"
    echo "   volumes) to start fresh with the new secrets."
    read -r -p "Regenerate .env with new secrets anyway? [y/N] " confirm
    if [[ "$confirm" =~ ^[Yy]$ ]]; then
        backup_env
        generate_env
    else
        echo "Keeping the existing .env file."
        add_missing_secrets
        source .env
    fi
else
    echo "Existing .env file detected (non-interactive mode, no --force-regen): keeping it as-is."
    add_missing_secrets
    source .env
fi

if [ -f .env ]; then
    chmod 600 .env
    # shellcheck disable=SC2046
    export $(grep -v '^#' .env | grep -v '^$' | xargs)
fi


# 3. Hydrate litellm/litellm.env (Langfuse callback & Presidio guardrails)
echo "Hydrating litellm/litellm.env (Langfuse API keys & Presidio)..."
cat <<EOF > litellm/litellm.env
# used by litellm
LITELLM_OTEL_V2=true
LANGFUSE_HOST="http://langfuse-web:3000"
PRESIDIO_API_BASE="http://betterleaks:8080/"
PRESIDIO_ANALYZER_API_BASE="http://betterleaks:8080/"
PRESIDIO_ANONYMIZER_API_BASE="http://betterleaks:8080/"
EOF

# Helper to hydrate templates safely using Python exact string replacement (immune to slashes, &, and backslashes)
hydrate_template() {
    local tpl="$1"
    local dest="$2"
    local var_name="$3"
    local var_value="$4"
    python3 -c "
import sys
tpl_path, dest_path, var_name, var_val = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
with open(tpl_path) as f:
    content = f.read()
target = '\${' + var_name + '}'
with open(dest_path, 'w') as f:
    f.write(content.replace(target, var_val))
" "$tpl" "$dest" "$var_name" "$var_value"
}

ensure_internal_tls_certificate() {
    [ "${TLS_MODE}" = "internal" ] || return 0

    local cert_file="traefik/certs/tls.crt"
    local key_file="traefik/certs/tls.key"
    mkdir -p traefik/certs

    if [ -f "$cert_file" ] && [ -f "$key_file" ]; then
        echo "Preserving the existing internal TLS certificate."
        return 0
    fi
    if [ -e "$cert_file" ] || [ -e "$key_file" ]; then
        echo "ERROR: Internal TLS certificate and key must either both exist or both be absent." >&2
        exit 1
    fi

    echo "Generating an internal wildcard TLS certificate for ${DOMAIN}..."
    openssl req -x509 -nodes -newkey rsa:2048 -sha256 -days 825 \
        -keyout "$key_file" \
        -out "$cert_file" \
        -subj "/CN=*.${DOMAIN}" \
        -addext "subjectAltName=DNS:${DOMAIN},DNS:*.${DOMAIN},DNS:vault,DNS:localhost,IP:127.0.0.1" \
        -addext "basicConstraints=critical,CA:TRUE" \
        -addext "keyUsage=critical,digitalSignature,keyEncipherment,keyCertSign" \
        >/dev/null 2>&1
    chmod 644 "$key_file"
    chmod 644 "$cert_file"
}

# 4bis. Prepare the Prometheus runtime configuration template.
echo "Preparing the Prometheus runtime configuration template (prometheus/prometheus.yml)..."
mkdir -p prometheus/targets.d
mkdir -p prometheus/textfile
cp prometheus/prometheus.yml.template prometheus/prometheus.yml
mkdir -p gatus/endpoints.d

# 4ter. Hydrate searxng/settings.yml
echo "Hydrating the SearXNG configuration (searxng/settings.yml)..."
hydrate_template searxng/settings.yml.template searxng/settings.yml SEARXNG_SECRET_KEY "${SEARXNG_SECRET_KEY}"

# 4ter-bis. Hydrate CoreDNS configuration (coredns/Corefile)
echo "Hydrating the CoreDNS configuration (coredns/Corefile)..."
mkdir -p coredns
escaped_domain="${DOMAIN//./\\.}"
python3 -c "
import sys
domain, esc_domain, lan_ip = sys.argv[1], sys.argv[2], sys.argv[3]
with open('coredns/Corefile.template') as f:
    content = f.read()
content = content.replace('\${DOMAIN}', domain).replace('\${ESCAPED_DOMAIN}', esc_domain).replace('\${LAN_IP}', lan_ip)
with open('coredns/Corefile', 'w') as f:
    f.write(content)
" "$DOMAIN" "$escaped_domain" "$LAN_IP"

# 4quater. Hydrate traefik configuration (traefik/traefik.yml & traefik/dynamic.yml)
ensure_internal_tls_certificate
python3 "$REPO_DIR/traefik/scripts/hydrate_traefik.py"

# 4quinquies. Generate a ready-to-use systemd unit file
echo "Generating llm-stack.service.generated (manual installation required)..."
hydrate_template llm-stack.service.template llm-stack.service.generated REPO_DIR "${REPO_DIR}"
echo "Generating optional Langfuse ingestion monitor systemd units..."
hydrate_template systemd/llm-stack-langfuse-ingestion.service.template systemd/llm-stack-langfuse-ingestion.service.generated REPO_DIR "${REPO_DIR}"
cp systemd/llm-stack-langfuse-ingestion.timer.template systemd/llm-stack-langfuse-ingestion.timer.generated

# 5. Point the repository path at its per-instance private RAM directory.
# start.sh creates the RAM target after boot and validates it before provisioning.
python3 "$REPO_DIR/vault/scripts/provision.py" --prepare-ram-link

echo "========================================================================"
echo " 🎉 Environment setup completed successfully!"
echo "========================================================================"
echo " 🔑 INITIAL ADMIN CREDENTIALS:"
echo "    Username : akadmin (or admin@${DOMAIN})"
echo "    Password : UI_PASSWORD in the local .env (never printed to logs)"
echo "    (Will be seeded into HashiCorp Vault upon first start)"
echo "------------------------------------------------------------------------"
echo " Next step: Start the stack by running:"
echo "   ./start.sh"
echo "   (or with full smoke test: ./start.sh --with-smoke-test)"
echo "========================================================================"
echo " 🌐 DNS RESOLUTION (${DNS_MODE} mode):"
if [ "$DNS_MODE" = "cloudflare" ]; then
    echo " Cloudflare Zero Trust Tunnel mode active (COMPOSE_PROFILES=cloudflare)."
    echo " Ensure CLOUDFLARE_TUNNEL_TOKEN is configured in .env and routes are pointed to this host."
elif [ "$DNS_MODE" = "coredns" ]; then
    echo " CoreDNS service active (COMPOSE_PROFILES=coredns) on ${COREDNS_BIND_IP}:53."
    echo " Apex '${DOMAIN}' and wildcard '*.${DOMAIN}' resolve automatically to ${LAN_IP}."
    echo " Configure your router DHCP or client DNS server settings to: ${COREDNS_BIND_IP}"
else
    echo " /etc/hosts (zero-dependency) mode active."
    echo " Add this line to /etc/hosts on any machine accessing the stack:"
    echo ""
    echo "    ${LAN_IP} ${DOMAIN} authentik.${DOMAIN} chat.${DOMAIN} grafana.${DOMAIN} litellm.${DOMAIN} langfuse.${DOMAIN} logs.${DOMAIN} searxng.${DOMAIN} s3.${DOMAIN} s3-console.${DOMAIN} clickhouse.${DOMAIN} qdrant.${DOMAIN} status.${DOMAIN} vault.${DOMAIN} traefik.${DOMAIN} alertmanager.${DOMAIN} docs.${DOMAIN} arch.${DOMAIN}"
    echo ""
fi
echo "========================================================================"
