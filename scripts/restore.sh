#!/usr/bin/env bash
# Restore a versioned encrypted backup with fail-closed preflight validation.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TMP_DIR="$(mktemp -d -t llm_stack_restore_XXXXXX)"
PAYLOAD_DIR="${TMP_DIR}/payload"
COMPONENT="all"
ARCHIVE=""
CONFIRM_VALUE="${CONFIRM_RESTORE:-}"
ALLOW_LITELLM_RESTART="${ALLOW_LITELLM_RESTART:-no}"
ALLOW_BEST_EFFORT_RESTORE="${ALLOW_BEST_EFFORT_RESTORE:-no}"
STOPPED_SERVICES=()

umask 077

usage() {
    cat <<'EOF'
Usage: scripts/restore.sh --archive FILE [--component NAME]
                          [--confirm ARCHIVE_BASENAME]
                          [--allow-litellm-restart]

Components: all, postgres, qdrant, open-webui, vault, clickhouse,
            seaweedfs, grafana, authentik-media, configs

Restoring all or postgres is refused unless --allow-litellm-restart is present.
Online/best-effort backups are refused unless ALLOW_BEST_EFFORT_RESTORE=yes.
EOF
}

while (($#)); do
    case "$1" in
        --archive)
            [[ $# -ge 2 ]] || { echo "ERROR: --archive requires a value." >&2; exit 2; }
            ARCHIVE="$2"
            shift 2
            ;;
        --component)
            [[ $# -ge 2 ]] || { echo "ERROR: --component requires a value." >&2; exit 2; }
            COMPONENT="$2"
            shift 2
            ;;
        --confirm)
            [[ $# -ge 2 ]] || { echo "ERROR: --confirm requires a value." >&2; exit 2; }
            CONFIRM_VALUE="$2"
            shift 2
            ;;
        --allow-litellm-restart)
            ALLOW_LITELLM_RESTART="yes"
            shift
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

case "${COMPONENT}" in
    all|postgres|qdrant|open-webui|vault|clickhouse|seaweedfs|grafana|authentik-media|configs) ;;
    *) echo "ERROR: Unsupported component: ${COMPONENT}" >&2; exit 2 ;;
esac
[[ -n "${ARCHIVE}" ]] || { echo "ERROR: --archive is required." >&2; exit 2; }
[[ -f "${ARCHIVE}" ]] || { echo "ERROR: Archive not found: ${ARCHIVE}" >&2; exit 1; }
ARCHIVE="$(cd "$(dirname "${ARCHIVE}")" && pwd)/$(basename "${ARCHIVE}")"
CHECKSUM_FILE="${ARCHIVE}.sha256"
[[ -f "${CHECKSUM_FILE}" ]] || { echo "ERROR: Required checksum is missing: ${CHECKSUM_FILE}" >&2; exit 1; }

if [[ "${COMPONENT}" == "all" || "${COMPONENT}" == "postgres" ]]; then
    [[ "${ALLOW_LITELLM_RESTART}" == "yes" ]] || {
        echo "ERROR: This restore interrupts LiteLLM. Explicit --allow-litellm-restart is required." >&2
        exit 1
    }
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
    fi
    [[ -n "${BACKUP_PASSPHRASE}" ]] || { echo "ERROR: Backup passphrase is empty." >&2; exit 1; }
}

stop_services() {
    local service
    local already_stopped
    local tracked
    for service in "$@"; do
        already_stopped="no"
        for tracked in "${STOPPED_SERVICES[@]}"; do
            [[ "${tracked}" == "${service}" ]] && already_stopped="yes"
        done
        [[ "${already_stopped}" == "yes" ]] && continue
        if [[ -n "$(docker compose -f "${REPO_ROOT}/docker-compose.yml" ps --status running -q "${service}")" ]]; then
            STOPPED_SERVICES+=("${service}")
            docker compose -f "${REPO_ROOT}/docker-compose.yml" stop "${service}"
        fi
    done
}

restore_volume() {
    local volume="$1"
    local archive_name="$2"
    local full_volume="llm-stack_${volume}"
    local source="${PAYLOAD_DIR}/volumes/${archive_name}"
    [[ -f "${source}" ]] || { echo "ERROR: Missing volume archive: ${archive_name}" >&2; exit 1; }
    docker volume inspect "${full_volume}" >/dev/null 2>&1 || docker volume create "${full_volume}" >/dev/null
    docker run --rm \
        -v "${full_volume}:/target" \
        -v "${source}:/backup.tar.gz:ro" \
        alpine:3.24.1 \
        sh -euc 'find /target -mindepth 1 -delete; tar xzf /backup.tar.gz -C /target'
}

load_passphrase

echo "[1/6] External checksum"
(
    cd "$(dirname "${ARCHIVE}")"
    sha256sum -c "$(basename "${CHECKSUM_FILE}")"
)

echo "[2/6] Safe archive inventory"
mkdir -p "${PAYLOAD_DIR}"
listing_file="${TMP_DIR}/archive.list"
openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -md sha256 \
    -in "${ARCHIVE}" -pass fd:3 3<<<"${BACKUP_PASSPHRASE}" | tar -tzf - > "${listing_file}"
if awk 'BEGIN { bad=0 } /(^|\/)\.\.($|\/)/ || /^\// { print "Unsafe archive entry: " $0 > "/dev/stderr"; bad=1 } END { exit bad }' "${listing_file}"; then
    :
else
    echo "ERROR: Archive contains an unsafe path." >&2
    exit 1
fi
openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 -md sha256 \
    -in "${ARCHIVE}" -pass fd:3 3<<<"${BACKUP_PASSPHRASE}" | tar -xzf - -C "${PAYLOAD_DIR}"

echo "[3/6] Manifest and payload integrity"
manifest="${PAYLOAD_DIR}/manifest.env"
[[ -f "${manifest}" ]] || { echo "ERROR: manifest.env is missing." >&2; exit 1; }
format_version="$(sed -n 's/^FORMAT_VERSION=//p' "${manifest}")"
consistency="$(sed -n 's/^CONSISTENCY=//p' "${manifest}")"
[[ "${format_version}" == "2" ]] || { echo "ERROR: Unsupported backup format: ${format_version}" >&2; exit 1; }
[[ "${consistency}" == "offline" || "${consistency}" == "online" ]] || { echo "ERROR: Invalid consistency value." >&2; exit 1; }
if [[ "${consistency}" != "offline" && "${ALLOW_BEST_EFFORT_RESTORE}" != "yes" ]]; then
    echo "ERROR: This is an online best-effort backup. Set ALLOW_BEST_EFFORT_RESTORE=yes to accept its consistency risk." >&2
    exit 1
fi
[[ -f "${PAYLOAD_DIR}/files.sha256" ]] || { echo "ERROR: files.sha256 is missing." >&2; exit 1; }
(
    cd "${PAYLOAD_DIR}"
    sha256sum -c files.sha256
)
required_files=(
    postgres/cluster.sql
    qdrant/collections.tsv
    configs/env
    configs/vault_keys.json
    configs/custom_models.yaml
    volumes/open-webui.tar.gz
    volumes/vault_data.tar.gz
    volumes/clickhouse_data.tar.gz
    volumes/clickhouse_logs.tar.gz
    volumes/seaweedfs_data.tar.gz
    volumes/grafana_data.tar.gz
    volumes/authentik_media.tar.gz
)
for required_file in "${required_files[@]}"; do
    [[ -f "${PAYLOAD_DIR}/${required_file}" ]] || {
        echo "ERROR: Required payload is missing: ${required_file}" >&2
        exit 1
    }
done

echo "[4/6] Destructive confirmation"
expected_confirmation="$(basename "${ARCHIVE}")"
if [[ -z "${CONFIRM_VALUE}" ]]; then
    read -r -p "Type ${expected_confirmation} to overwrite ${COMPONENT} data: " CONFIRM_VALUE
fi
[[ "${CONFIRM_VALUE}" == "${expected_confirmation}" ]] || {
    echo "ERROR: Confirmation did not match; no service or data was changed." >&2
    exit 1
}

echo "[5/6] Restore ${COMPONENT}"
if [[ "${COMPONENT}" == "all" || "${COMPONENT}" == "configs" ]]; then
    install -m 600 "${PAYLOAD_DIR}/configs/env" "${REPO_ROOT}/.env"
    install -m 600 "${PAYLOAD_DIR}/configs/vault_keys.json" "${REPO_ROOT}/.vault_keys.json"
    install -m 600 "${PAYLOAD_DIR}/configs/custom_models.yaml" "${REPO_ROOT}/litellm/custom_models.yaml"
    if [[ -d "${PAYLOAD_DIR}/configs/targets.d" ]]; then
        mkdir -p "${REPO_ROOT}/prometheus/targets.d"
        find "${REPO_ROOT}/prometheus/targets.d" -mindepth 1 -delete
        cp -a "${PAYLOAD_DIR}/configs/targets.d/." "${REPO_ROOT}/prometheus/targets.d/"
    fi
fi

if [[ "${COMPONENT}" == "all" || "${COMPONENT}" == "postgres" ]]; then
    stop_services litellm langfuse-web langfuse-worker authentik-server authentik-worker chouse-ui
    docker compose -f "${REPO_ROOT}/docker-compose.yml" exec -T postgres \
        psql -X -U postgres -v ON_ERROR_STOP=0 -f - < "${PAYLOAD_DIR}/postgres/cluster.sql" \
        > "${TMP_DIR}/postgres-restore.log" 2>&1
    docker compose -f "${REPO_ROOT}/docker-compose.yml" exec -T postgres \
        psql -X -U postgres -Atqc "SELECT datname FROM pg_database WHERE datname IN ('authentik','langfuse','chouse_ui') ORDER BY datname" \
        > "${TMP_DIR}/postgres-databases"
    diff -u <(printf '%s\n' authentik chouse_ui langfuse) "${TMP_DIR}/postgres-databases"
fi

if [[ "${COMPONENT}" == "all" || "${COMPONENT}" == "qdrant" ]]; then
    stop_services open-webui
    QDRANT_API_KEY="$(sed -n 's/^QDRANT__SERVICE__API_KEY=//p' "${REPO_ROOT}/vault/secrets_ram/qdrant.env" | tail -n 1 | tr -d '"')"
    [[ -n "${QDRANT_API_KEY}" ]] || { echo "ERROR: Qdrant API key is unavailable." >&2; exit 1; }
    qdrant_header_file="${TMP_DIR}/qdrant_header"
    printf 'api-key: %s\n' "${QDRANT_API_KEY}" > "${qdrant_header_file}"
    while IFS=$'\t' read -r collection snapshot_file; do
        [[ -n "${collection}" && -n "${snapshot_file}" ]] || continue
        curl --fail --silent --show-error -X POST \
            -H @"${qdrant_header_file}" \
            -F "snapshot=@${PAYLOAD_DIR}/qdrant/${snapshot_file}" \
            "http://127.0.0.1:6333/collections/${collection}/snapshots/upload?priority=snapshot" >/dev/null
    done < "${PAYLOAD_DIR}/qdrant/collections.tsv"
fi

if [[ "${COMPONENT}" == "all" || "${COMPONENT}" == "open-webui" ]]; then
    stop_services open-webui
    restore_volume open-webui open-webui.tar.gz
fi
if [[ "${COMPONENT}" == "all" || "${COMPONENT}" == "clickhouse" ]]; then
    stop_services langfuse-web langfuse-worker chouse-ui clickhouse
    restore_volume langfuse_clickhouse_data clickhouse_data.tar.gz
    restore_volume langfuse_clickhouse_logs clickhouse_logs.tar.gz
fi
if [[ "${COMPONENT}" == "all" || "${COMPONENT}" == "seaweedfs" ]]; then
    stop_services langfuse-worker seaweedfs
    restore_volume seaweedfs_data seaweedfs_data.tar.gz
fi
if [[ "${COMPONENT}" == "all" || "${COMPONENT}" == "grafana" ]]; then
    stop_services grafana
    restore_volume grafana_data grafana_data.tar.gz
fi
if [[ "${COMPONENT}" == "all" || "${COMPONENT}" == "authentik-media" ]]; then
    stop_services authentik-server authentik-worker
    restore_volume authentik_media authentik_media.tar.gz
fi
if [[ "${COMPONENT}" == "all" || "${COMPONENT}" == "vault" ]]; then
    stop_services vault-agent vault
    install -m 600 "${PAYLOAD_DIR}/configs/vault_keys.json" "${REPO_ROOT}/.vault_keys.json"
    restore_volume vault_data vault_data.tar.gz
fi

resume_services

echo "[6/6] Runtime reconciliation"
if [[ "${COMPONENT}" == "all" ]]; then
    "${REPO_ROOT}/start.sh"
else
    docker compose -f "${REPO_ROOT}/docker-compose.yml" ps
fi
echo "Restore completed successfully from ${ARCHIVE}."
echo "Run ./smoke_test.sh before declaring recovery complete."
