#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

require_uat_run
require_uat_cache

git -C "${UAT_REPO_ROOT}" cat-file -e "${UAT_CANDIDATE_SHA}^{commit}"

if [[ "${UAT_WORKTREE}" != "${UAT_REPO_ROOT}"/uat/runtime/worktree ]]; then
    echo "ERROR: UAT_WORKTREE must be ${UAT_REPO_ROOT}/uat/runtime/worktree." >&2
    exit 1
fi

available_memory_mib="$(awk '/MemAvailable:/ { print int($2 / 1024) }' /proc/meminfo)"
available_disk_mib="$(df -Pm "${UAT_REPO_ROOT}" | awk 'NR == 2 { print $4 }')"

if (( available_memory_mib < UAT_MIN_AVAILABLE_MEMORY_MIB )); then
    echo "ERROR: UAT requires ${UAT_MIN_AVAILABLE_MEMORY_MIB} MiB available RAM; found ${available_memory_mib} MiB." >&2
    exit 1
fi
if (( available_disk_mib < UAT_MIN_AVAILABLE_DISK_MIB )); then
    echo "ERROR: UAT requires ${UAT_MIN_AVAILABLE_DISK_MIB} MiB free disk; found ${available_disk_mib} MiB." >&2
    exit 1
fi

if grep -q '/var/run/docker.sock' "${UAT_COMPOSE_FILE}"; then
    echo "ERROR: The UAT controller must never mount the production Docker socket." >&2
    exit 1
fi

uat_compose config --quiet

echo "UAT preflight passed."
echo "Candidate SHA: ${UAT_CANDIDATE_SHA}"
echo "Run ID: ${UAT_RUN_ID}"
echo "UAT image cache: ${UAT_DOCKER_CACHE_VOLUME}"
echo "UAT Ollama model cache: ${UAT_OLLAMA_MODEL_VOLUME}"
echo "Available RAM: ${available_memory_mib} MiB"
echo "Available disk: ${available_disk_mib} MiB"
