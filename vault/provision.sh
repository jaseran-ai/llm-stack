#!/usr/bin/env bash
set -e
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

if [ -f "$REPO_DIR/.env" ]; then
    set -a
    source "$REPO_DIR/.env"
    set +a
fi

# trust.crt bundles the internal CA (Vault listener) and the ingress CA (services behind Traefik).
export SSL_CERT_FILE="$REPO_DIR/traefik/certs/trust.crt"
export VAULT_CACERT="$REPO_DIR/traefik/certs/internal-ca.crt"

echo "Ensuring Vault storage permissions..."
# Plain 'docker exec' on purpose: 'docker compose exec' validates every service's env_file,
# and the vault/secrets_ram/*.env files do not exist yet on a fresh install (Vault Agent
# renders them after this step), which made the ownership fix silently never run.
if ! docker exec -u 0 vault chown -R 100:100 /vault/data \
    || ! docker exec -u 0 vault chmod -R 777 /vault/data; then
    echo "WARNING: could not fix /vault/data ownership; Vault initialization may fail." >&2
fi

echo "Provisioning Vault (initialization, unseal, secret seeding)..."
python3 "$REPO_DIR/vault/scripts/provision.py" "$@"
