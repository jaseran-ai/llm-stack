#!/usr/bin/env bash
# Compatibility entry point for the canonical encrypted restore implementation.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKUP=""
COMPONENT=""
PASSTHROUGH=()

for argument in "$@"; do
    case "${argument}" in
        BACKUP=*) BACKUP="${argument#BACKUP=}" ;;
        COMPONENT=*) COMPONENT="${argument#COMPONENT=}" ;;
        *) PASSTHROUGH+=("${argument}") ;;
    esac
done

if [[ -z "${BACKUP}" ]]; then
    exec "${REPO_ROOT}/scripts/restore.sh" "${PASSTHROUGH[@]}"
fi

if [[ -f "${BACKUP}" ]]; then
    archive="${BACKUP}"
elif [[ -f "${REPO_ROOT}/backups/${BACKUP}" ]]; then
    archive="${REPO_ROOT}/backups/${BACKUP}"
elif [[ -f "${REPO_ROOT}/backups/llm_stack_backup_${BACKUP}.tar.gz.enc" ]]; then
    archive="${REPO_ROOT}/backups/llm_stack_backup_${BACKUP}.tar.gz.enc"
else
    echo "ERROR: No canonical encrypted archive matches BACKUP=${BACKUP}." >&2
    echo "Available archives:" >&2
    find "${REPO_ROOT}/backups" -maxdepth 1 -type f -name '*.tar.gz.enc' -printf '  %f\n' 2>/dev/null | sort >&2
    exit 1
fi

arguments=(--archive "${archive}")
[[ -z "${COMPONENT}" ]] || arguments+=(--component "${COMPONENT}")
[[ "${ALLOW_LITELLM_RESTART:-no}" != "yes" ]] || arguments+=(--allow-litellm-restart)
exec "${REPO_ROOT}/scripts/restore.sh" "${arguments[@]}" "${PASSTHROUGH[@]}"
