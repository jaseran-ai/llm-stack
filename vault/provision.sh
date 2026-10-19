#!/usr/bin/env bash
set -e
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

if [ -f "$REPO_DIR/.env" ]; then
    set -a
    source "$REPO_DIR/.env"
    set +a
fi

export SSL_CERT_FILE="$REPO_DIR/traefik/certs/tls.crt"
export VAULT_CACERT="$REPO_DIR/traefik/certs/tls.crt"

echo "Ensuring Vault storage permissions..."
docker compose exec -T -u 0 vault chown -R 100:100 /vault/data 2>/dev/null || true
docker compose exec -T -u 0 vault chmod -R 777 /vault/data 2>/dev/null || true

echo "Provisioning Vault (initialization, unseal, secret seeding)..."
python3 "$REPO_DIR/vault/scripts/provision.py" "$@"
