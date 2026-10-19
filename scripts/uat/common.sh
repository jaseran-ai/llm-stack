#!/usr/bin/env bash
set -euo pipefail

UAT_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UAT_REPO_ROOT="$(cd "${UAT_SCRIPT_DIR}/../.." && pwd)"
UAT_ENV_FILE="${UAT_REPO_ROOT}/uat/.env"
UAT_RUN_ENV_FILE="${UAT_REPO_ROOT}/uat/runtime/run.env"
UAT_COMPOSE_FILE="${UAT_REPO_ROOT}/uat/docker-compose.yml"
UAT_CERTS_DIR="${UAT_REPO_ROOT}/uat/runtime/certs"

if [[ ! -f "${UAT_ENV_FILE}" ]]; then
    echo "ERROR: Missing uat/.env. Copy uat/uat.env.example and set every value." >&2
    exit 1
fi

set -a
# shellcheck disable=SC1090
source "${UAT_ENV_FILE}"
set +a

if [[ -f "${UAT_RUN_ENV_FILE}" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "${UAT_RUN_ENV_FILE}"
    set +a
fi

required_variables=(
    UAT_CANDIDATE_SHA
    UAT_DOCKER_CACHE_VOLUME
    UAT_OLLAMA_MODEL_VOLUME
    UAT_DOMAIN
    UAT_WORKTREE
    UAT_DOCKER_PORT
    UAT_MIN_AVAILABLE_MEMORY_MIB
    UAT_MIN_AVAILABLE_DISK_MIB
)
for variable_name in "${required_variables[@]}"; do
    if [[ -z "${!variable_name:-}" ]]; then
        echo "ERROR: ${variable_name} must be set explicitly in uat/.env." >&2
        exit 1
    fi
done

require_uat_run() {
    if [[ ! -f "${UAT_RUN_ENV_FILE}" ]] || [[ -z "${UAT_RUN_ID:-}" ]]; then
        echo "ERROR: No disposable UAT run is prepared. Run make uat-setup first." >&2
        exit 1
    fi
    if [[ ! "${UAT_SECRETS_RAM_ID:-}" =~ ^[0-9a-f]{16}$ ]]; then
        echo "ERROR: UAT_SECRETS_RAM_ID must be a generated 16-character hex ID." >&2
        exit 1
    fi
}

require_uat_cache() {
    if [[ ! "${UAT_DOCKER_CACHE_VOLUME}" =~ ^llm-stack-uat-docker-(cache|data)-[a-z0-9-]+$ ]]; then
        echo "ERROR: UAT_DOCKER_CACHE_VOLUME must be an isolated UAT cache volume name." >&2
        exit 1
    fi
    if [[ ! "${UAT_OLLAMA_MODEL_VOLUME}" =~ ^llm-stack-uat-ollama-model-cache(-[a-z0-9-]+)?$ ]]; then
        echo "ERROR: UAT_OLLAMA_MODEL_VOLUME must be an isolated UAT model cache volume name." >&2
        exit 1
    fi
    if [[ "${UAT_OLLAMA_MODEL_VOLUME}" == "${UAT_DOCKER_CACHE_VOLUME}" ]]; then
        echo "ERROR: Docker and Ollama must use separate UAT cache volumes." >&2
        exit 1
    fi
}

uat_compose() {
    require_uat_run
    docker compose --env-file "${UAT_ENV_FILE}" --env-file "${UAT_RUN_ENV_FILE}" -f "${UAT_COMPOSE_FILE}" "$@"
}

export UAT_REPO_ROOT UAT_ENV_FILE UAT_RUN_ENV_FILE UAT_COMPOSE_FILE UAT_CERTS_DIR
