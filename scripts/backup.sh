#!/usr/bin/env bash
# Create a versioned, encrypted backup of the state required to recover llm-stack.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
BACKUP_ROOT="${BACKUP_ROOT:-${REPO_ROOT}/backups}"
BACKUP_KEEP_DAYS="${BACKUP_KEEP_DAYS:-7}"
BACKUP_CONSISTENCY="${BACKUP_CONSISTENCY:-online}"
TIMESTAMP="$(date -u +'%Y%m%d_%H%M%S')"
BACKUP_BASENAME="llm_stack_backup_${TIMESTAMP}"
TMP_DIR="$(mktemp -d -t llm_stack_backup_XXXXXX)"
PAYLOAD_DIR="${TMP_DIR}/payload"
STOPPED_SERVICES=()

umask 077

usage() {
    cat <<'EOF'
Usage: scripts/backup.sh [--consistency online|offline]

Environment:
  BACKUP_PASSPHRASE   Encryption passphrase. Read from .env when omitted.
  BACKUP_ROOT         Archive destination (default: repository backups/).
  BACKUP_KEEP_DAYS    Retention in days (default: 7; 0 disables pruning).

Online mode does not interrupt services and records raw-volume captures as
best-effort. Offline mode briefly stops writers before raw-volume capture and
is required for a disaster-recovery-qualified backup.
EOF
}

while (($#)); do
    case "$1" in
        --consistency)
            [[ $# -ge 2 ]] || { echo "ERROR: --consistency requires a value." >&2; exit 2; }
            BACKUP_CONSISTENCY="$2"
            shift 2
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            echo "ERROR: Unknown argument: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

if [[ "${BACKUP_CONSISTENCY}" != "online" && "${BACKUP_CONSISTENCY}" != "offline" ]]; then
    echo "ERROR: BACKUP_CONSISTENCY must be online or offline." >&2
    exit 2
fi
if [[ ! "${BACKUP_KEEP_DAYS}" =~ ^[0-9]+$ ]]; then
    echo "ERROR: BACKUP_KEEP_DAYS must be a non-negative integer." >&2
    exit 2
fi

resume_services() {
    local service
    local vault_was_stopped="no"
    local remaining_services=()
    ((${#STOPPED_SERVICES[@]})) || return 0
    for service in "${STOPPED_SERVICES[@]}"; do
        if [[ "${service}" == "vault" ]]; then
            vault_was_stopped="yes"
        else
            remaining_services+=("${service}")
        fi
    done
    if [[ "${vault_was_stopped}" == "yes" ]]; then
        docker compose -f "${REPO_ROOT}/docker-compose.yml" start vault >/dev/null
        bash "${REPO_ROOT}/vault/provision.sh" --skip-oidc >/dev/null
    fi
    if ((${#remaining_services[@]})); then
        docker compose -f "${REPO_ROOT}/docker-compose.yml" start "${remaining_services[@]}" >/dev/null
    fi
    STOPPED_SERVICES=()
}

cleanup() {
    local exit_code=$?
    trap - EXIT INT TERM
    set +e
    resume_services
    rm -rf -- "${TMP_DIR}"
    if ((exit_code != 0)); then
        rm -f -- "${BACKUP_ROOT}/${BACKUP_BASENAME}.tar.gz.enc" \
            "${BACKUP_ROOT}/${BACKUP_BASENAME}.tar.gz.enc.sha256"
        echo "ERROR: Backup failed; incomplete output was removed." >&2
    fi
    exit "${exit_code}"
}
trap cleanup EXIT INT TERM

load_passphrase() {
    if [[ -z "${BACKUP_PASSPHRASE:-}" && -f "${REPO_ROOT}/.env" ]]; then
        BACKUP_PASSPHRASE="$(sed -n 's/^BACKUP_PASSPHRASE=//p' "${REPO_ROOT}/.env" | tail -n 1 | sed 's/^["'"'"' ]*//;s/["'"'"' ]*$//')"
    fi
    if [[ -z "${BACKUP_PASSPHRASE:-}" ]]; then
        read -r -s -p "Backup encryption passphrase: " BACKUP_PASSPHRASE
        echo
        read -r -s -p "Confirm passphrase: " confirmation
        echo
        [[ "${BACKUP_PASSPHRASE}" == "${confirmation}" ]] || {
            echo "ERROR: Passphrases do not match." >&2
            exit 1
        }
    fi
    ((${#BACKUP_PASSPHRASE} >= 12)) || {
        echo "ERROR: Backup passphrase must contain at least 12 characters." >&2
        exit 1
    }
}

require_command() {
    command -v "$1" >/dev/null 2>&1 || {
        echo "ERROR: Required command not found: $1" >&2
        exit 1
    }
}

require_running_service() {
    local service="$1"
    [[ -n "$(docker compose -f "${REPO_ROOT}/docker-compose.yml" ps --status running -q "${service}")" ]] || {
        echo "ERROR: Required service is not running: ${service}" >&2
        exit 1
    }
}

stop_writers() {
    local service
    [[ "${BACKUP_CONSISTENCY}" == "offline" ]] || return 0
    for service in "$@"; do
        if [[ -n "$(docker compose -f "${REPO_ROOT}/docker-compose.yml" ps --status running -q "${service}")" ]]; then
            STOPPED_SERVICES+=("${service}")
        fi
    done
    if ((${#STOPPED_SERVICES[@]})); then
        echo "Stopping raw-volume writers: ${STOPPED_SERVICES[*]}"
        docker compose -f "${REPO_ROOT}/docker-compose.yml" stop "${STOPPED_SERVICES[@]}"
    fi
}

volume_archive() {
    local volume="$1"
    local destination="$2"
    local full_volume="llm-stack_${volume}"
    docker volume inspect "${full_volume}" >/dev/null 2>&1 || {
        echo "ERROR: Required Docker volume does not exist: ${full_volume}" >&2
        exit 1
    }
    docker run --rm \
        -v "${full_volume}:/source:ro" \
        -v "${PAYLOAD_DIR}/volumes:/backup" \
        alpine:3.24.1 \
        tar czf "/backup/${destination}" -C /source .
    tar -tzf "${PAYLOAD_DIR}/volumes/${destination}" >/dev/null
}

require_command docker
require_command curl
require_command openssl
require_command python3
require_command sha256sum
require_command tar
load_passphrase

mkdir -p "${BACKUP_ROOT}" "${PAYLOAD_DIR}/postgres" \
    "${PAYLOAD_DIR}/qdrant" "${PAYLOAD_DIR}/volumes" "${PAYLOAD_DIR}/configs"

for service in postgres qdrant vault clickhouse seaweedfs open-webui grafana authentik-server; do
    require_running_service "${service}"
done

echo "[1/6] PostgreSQL logical cluster dump"
docker compose -f "${REPO_ROOT}/docker-compose.yml" exec -T postgres \
    pg_dumpall -U postgres --clean --if-exists > "${PAYLOAD_DIR}/postgres/cluster.sql"
[[ -s "${PAYLOAD_DIR}/postgres/cluster.sql" ]] || {
    echo "ERROR: PostgreSQL dump is empty." >&2
    exit 1
}

echo "[2/6] Qdrant collection snapshots"
QDRANT_API_KEY=""
if [[ -f "${REPO_ROOT}/vault/secrets_ram/qdrant.env" ]]; then
    QDRANT_API_KEY="$(sed -n 's/^QDRANT__SERVICE__API_KEY=//p' "${REPO_ROOT}/vault/secrets_ram/qdrant.env" | tail -n 1 | tr -d '"')"
fi
[[ -n "${QDRANT_API_KEY}" ]] || {
    echo "ERROR: Qdrant API key is unavailable." >&2
    exit 1
}
qdrant_header_file="${TMP_DIR}/qdrant_header"
printf 'api-key: %s\n' "${QDRANT_API_KEY}" > "${qdrant_header_file}"
collections_json="$(curl --fail --silent --show-error -H @"${qdrant_header_file}" http://127.0.0.1:6333/collections)"
mapfile -t collections < <(python3 -c 'import json,sys; print("\n".join(item["name"] for item in json.load(sys.stdin)["result"]["collections"]))' <<<"${collections_json}")
: > "${PAYLOAD_DIR}/qdrant/collections.tsv"
for collection in "${collections[@]}"; do
    [[ "${collection}" =~ ^[A-Za-z0-9._-]+$ ]] || {
        echo "ERROR: Unsupported Qdrant collection name: ${collection}" >&2
        exit 1
    }
    snapshot_json="$(curl --fail --silent --show-error -X POST -H @"${qdrant_header_file}" \
        "http://127.0.0.1:6333/collections/${collection}/snapshots?wait=true")"
    snapshot_name="$(python3 -c 'import json,sys; print(json.load(sys.stdin)["result"]["name"])' <<<"${snapshot_json}")"
    [[ -n "${snapshot_name}" ]] || { echo "ERROR: Qdrant returned no snapshot for ${collection}." >&2; exit 1; }
    curl --fail --silent --show-error -H @"${qdrant_header_file}" \
        "http://127.0.0.1:6333/collections/${collection}/snapshots/${snapshot_name}" \
        -o "${PAYLOAD_DIR}/qdrant/${collection}.snapshot"
    printf '%s\t%s\n' "${collection}" "${collection}.snapshot" >> "${PAYLOAD_DIR}/qdrant/collections.tsv"
    curl --fail --silent --show-error -X DELETE -H @"${qdrant_header_file}" \
        "http://127.0.0.1:6333/collections/${collection}/snapshots/${snapshot_name}" >/dev/null
done

echo "[3/6] Configuration and recovery keys"
install -m 600 "${REPO_ROOT}/.env" "${PAYLOAD_DIR}/configs/env"
install -m 600 "${REPO_ROOT}/.vault_keys.json" "${PAYLOAD_DIR}/configs/vault_keys.json"
install -m 600 "${REPO_ROOT}/litellm/custom_models.yaml" "${PAYLOAD_DIR}/configs/custom_models.yaml"
if [[ -d "${REPO_ROOT}/prometheus/targets.d" ]]; then
    cp -a "${REPO_ROOT}/prometheus/targets.d" "${PAYLOAD_DIR}/configs/targets.d"
fi

echo "[4/6] Stateful Docker volumes (${BACKUP_CONSISTENCY})"
if [[ "${BACKUP_CONSISTENCY}" == "online" ]]; then
    echo "WARNING: Raw-volume captures are best-effort because writers remain online." >&2
else
    stop_writers open-webui langfuse-web langfuse-worker chouse-ui clickhouse seaweedfs \
        grafana authentik-server authentik-worker vault-agent vault
fi
volume_archive open-webui open-webui.tar.gz
volume_archive vault_data vault_data.tar.gz
volume_archive langfuse_clickhouse_data clickhouse_data.tar.gz
volume_archive langfuse_clickhouse_logs clickhouse_logs.tar.gz
volume_archive seaweedfs_data seaweedfs_data.tar.gz
volume_archive grafana_data grafana_data.tar.gz
volume_archive authentik_media authentik_media.tar.gz
resume_services

echo "[5/6] Manifest and payload integrity"
cat > "${PAYLOAD_DIR}/manifest.env" <<EOF
FORMAT_VERSION=2
CREATED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
CONSISTENCY=${BACKUP_CONSISTENCY}
PROJECT=llm-stack
EOF
(
    cd "${PAYLOAD_DIR}"
    find . -type f -print0 | sort -z | xargs -0 sha256sum > "${TMP_DIR}/files.sha256"
    mv "${TMP_DIR}/files.sha256" files.sha256
)

echo "[6/6] Encryption and external checksum"
final_archive="${BACKUP_ROOT}/${BACKUP_BASENAME}.tar.gz.enc"
final_checksum="${final_archive}.sha256"
tar -czf - -C "${PAYLOAD_DIR}" . | \
    openssl enc -aes-256-cbc -salt -pbkdf2 -iter 200000 -md sha256 \
        -out "${final_archive}" -pass fd:3 3<<<"${BACKUP_PASSPHRASE}"
(
    cd "${BACKUP_ROOT}"
    sha256sum "$(basename "${final_archive}")" > "$(basename "${final_checksum}")"
)
chmod 600 "${final_archive}" "${final_checksum}"

if ((BACKUP_KEEP_DAYS > 0)); then
    find "${BACKUP_ROOT}" -maxdepth 1 -type f \
        \( -name 'llm_stack_backup_*.tar.gz.enc' -o -name 'llm_stack_backup_*.tar.gz.enc.sha256' \) \
        -mtime "+${BACKUP_KEEP_DAYS}" -delete
fi

echo "Backup completed: ${final_archive}"
echo "Consistency: ${BACKUP_CONSISTENCY}"
