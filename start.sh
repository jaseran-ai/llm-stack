#!/usr/bin/env bash
# ==============================================================================
# LLM Stack - Service Startup & Runtime Provisioner
# Starts containers through explicit readiness gates (Vault -> Vault Agent ->
# Authentik reconciliation -> dependent services) and executes post-startup
# per-tool provisioning.
# ==============================================================================

set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

show_help() {
    cat <<EOF
========================================================================
 LLM Stack Startup Script
========================================================================
Usage: ./start.sh [OPTIONS] [SERVICES...]

Options:
  --with-smoke-test       Run ./smoke_test.sh after services are up.
  --skip-smoke-test       Do not run ./smoke_test.sh (default).
  -h, --help              Show this help message and exit.

Examples:
  ./start.sh
  ./start.sh traefik clickhouse chouse-ui
  ./start.sh --with-smoke-test
========================================================================
EOF
    exit 0
}

RUN_SMOKE_TEST=false
SERVICES=()
for arg in "$@"; do
    case "$arg" in
        -h|--help)
            show_help
            ;;
        --with-smoke-test)
            RUN_SMOKE_TEST=true
            ;;
        --skip-smoke-test)
            RUN_SMOKE_TEST=false
            ;;
        *)
            SERVICES+=("$arg")
            ;;
    esac
done

is_service_requested() {
    local target="$1"
    if [ ${#SERVICES[@]} -eq 0 ]; then
        return 0
    fi
    for s in "${SERVICES[@]}"; do
        if [ "$s" = "$target" ]; then
            return 0
        fi
    done
    return 1
}

# 1. Ensure .env exists
if [ ! -f .env ]; then
    echo "ERROR: .env file not found!"
    echo "Please run ./setup.sh first to configure your environment and generate secrets."
    exit 1
fi

# shellcheck disable=SC2046
export $(grep -v '^#' .env | grep -v '^$' | xargs)

if [ -z "${DOMAIN:-}" ]; then
    echo "ERROR: DOMAIN is not defined in .env!"
    echo "Please run ./setup.sh or define DOMAIN in .env."
    exit 1
fi
echo "========================================================================"
echo " 🚀 Starting LLM Stack (${DOMAIN})"
echo "========================================================================"

# 2. Recreate the private RAM target after reboot and refuse persistent storage.
python3 "$REPO_DIR/vault/scripts/provision.py" --ensure-ram

# 3. Migrate Grafana datasource UIDs if needed before container start
if is_service_requested grafana; then
    bash "$REPO_DIR/grafana/provision.sh"
fi

# 4. Start Vault container and initialize/unseal
echo "Starting HashiCorp Vault..."
docker compose up -d vault
bash "$REPO_DIR/vault/provision.sh" --skip-oidc

# 5. Start Vault Agent to render secrets into RAM tmpfs
echo "Starting Vault Agent..."
docker compose up -d vault-agent

# Wait for vault-agent to become healthy (renders secret files in vault/secrets_ram/)
echo "Waiting for secrets to be rendered into memory..."
for _ in $(seq 1 30); do
    if docker compose ps vault-agent 2>/dev/null | grep -q "(healthy)"; then
        break
    fi
    sleep 1
done
if ! docker compose ps vault-agent 2>/dev/null | grep -q "(healthy)"; then
    echo "ERROR: Vault Agent did not become healthy; refusing to start services without runtime secrets." >&2
    exit 1
fi

if is_service_requested prometheus; then
    echo "Hydrating the Prometheus configuration from Vault-rendered secrets..."
    bash "$REPO_DIR/prometheus/scripts/hydrate_config.sh" "$REPO_DIR"
fi


# 6. Run the declarative Authentik reconciliation gate. Compose starts its
# PostgreSQL/server/worker dependencies and waits for both Authentik health
# contracts before launching the one-shot job.
echo "Running the Authentik provisioning gate..."
docker compose --profile provisioning up -d --force-recreate authentik-provision
if ! docker compose --profile provisioning wait authentik-provision; then
    echo "ERROR: Authentik provisioning failed; refusing to start dependent services." >&2
    docker compose logs authentik-provision --since=10m >&2
    exit 1
fi

# 7. Start services, then wait for the applications whose provisioners
# run immediately below. Open WebUI keeps its dedicated API wait,
# provisioning, restart, and second API wait later in this script.
if is_service_requested docs-user && ! docker image inspect llm-stack-docs-user:local >/dev/null 2>&1; then
    echo "Building docs-user container image..."
    bash "$REPO_DIR/docs/publish.sh" user
fi
if is_service_requested docs-architecture && ! docker image inspect llm-stack-docs-architecture:local >/dev/null 2>&1; then
    echo "Building docs-architecture container image..."
    bash "$REPO_DIR/docs/publish.sh" architecture
fi

if [ ${#SERVICES[@]} -eq 0 ]; then
    echo "Starting all stack containers..."
    docker compose up -d
    echo "Waiting for immediate provisioning targets..."
    docker compose up -d --wait --wait-timeout 600 chouse-ui langfuse-web litellm
else
    echo "Starting requested services: ${SERVICES[*]}..."
    docker compose up -d "${SERVICES[@]}"
    wait_targets=()
    for svc in chouse-ui langfuse-web litellm; do
        if is_service_requested "$svc"; then
            wait_targets+=("$svc")
        fi
    done
    if [ ${#wait_targets[@]} -gt 0 ]; then
        echo "Waiting for immediate provisioning targets: ${wait_targets[*]}..."
        docker compose up -d --wait --wait-timeout 600 "${wait_targets[@]}"
    fi
fi

# 8. Execute remaining post-startup per-tool provisioning
echo "Running post-startup tool provisioning..."
if is_service_requested ollama; then
    bash "$REPO_DIR/ollama/provision.sh"
fi

echo "Configuring Vault OIDC after Authentik provisioning..."
bash "$REPO_DIR/vault/provision.sh" --oidc-only

if is_service_requested chouse-ui || is_service_requested clickhouse; then
    bash "$REPO_DIR/clickhouse/provision.sh"
fi
if is_service_requested litellm; then
    bash "$REPO_DIR/litellm/provision.sh"
fi

if is_service_requested open-webui; then
    echo "Waiting for the Open WebUI API before provisioning..."
    for _ in $(seq 1 180); do
        if curl -fsS "http://127.0.0.1:${OPEN_WEBUI_PORT}/health" >/dev/null; then
            break
        fi
        sleep 1
    done
    if ! curl -fsS "http://127.0.0.1:${OPEN_WEBUI_PORT}/health" >/dev/null; then
        echo "ERROR: Open WebUI API did not become healthy before provisioning." >&2
        exit 1
    fi

    bash "$REPO_DIR/open-webui/provision.sh"
    echo "Restarting Open WebUI to activate provisioned models..."
    docker compose restart open-webui
    echo "Waiting for Open WebUI after model activation..."
    for _ in $(seq 1 180); do
        if curl -fsS "http://127.0.0.1:${OPEN_WEBUI_PORT}/health" >/dev/null; then
            break
        fi
        sleep 1
    done
    if ! curl -fsS "http://127.0.0.1:${OPEN_WEBUI_PORT}/health" >/dev/null; then
        echo "ERROR: Open WebUI did not become healthy after model activation." >&2
        exit 1
    fi
fi

echo "========================================================================"
echo " 🎉 LLM Stack started successfully!"
echo "========================================================================"
echo " 🔑 INITIAL ADMIN CREDENTIALS:"
echo "    Username : akadmin (or admin@${DOMAIN})"
echo "    Password : UI_PASSWORD in the local .env (never printed to logs)"
echo "    (Stored in .env and HashiCorp Vault — change upon first login)"
echo "------------------------------------------------------------------------"
echo " Application Dashboard : https://${DOMAIN} (or https://authentik.${DOMAIN}/if/user/)"
echo " Authentik SSO Portal  : https://authentik.${DOMAIN}"
echo " Traefik Ingress       : https://traefik.${DOMAIN}"
echo " Grafana Dashboards    : https://grafana.${DOMAIN}"
echo " Open-WebUI Chat       : https://chat.${DOMAIN}"
echo " LiteLLM Proxy Gateway : https://litellm.${DOMAIN}"
echo " Langfuse LLMOps       : https://langfuse.${DOMAIN}"
echo " CHouse UI             : https://clickhouse.${DOMAIN}"
echo " Vault Secrets Engine  : https://vault.${DOMAIN}"
echo " User Documentation    : https://docs.${DOMAIN}"
echo " Architecture Docs     : https://arch.${DOMAIN}"
echo "========================================================================"

if [ "$RUN_SMOKE_TEST" = true ]; then
    echo "Running end-to-end smoke test..."
    ./smoke_test.sh
fi
