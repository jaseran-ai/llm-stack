#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

"${SCRIPT_DIR}/preflight.sh"

identity_file="${UAT_WORKTREE}/.uat-identity"
if [[ ! -f "${identity_file}" ]] || ! grep -qx "CANDIDATE_SHA=${UAT_CANDIDATE_SHA}" "${identity_file}" || ! grep -qx "RUN_ID=${UAT_RUN_ID}" "${identity_file}" || ! grep -qx "DOCKER_CACHE_VOLUME=${UAT_DOCKER_CACHE_VOLUME}" "${identity_file}" || ! grep -qx "OLLAMA_MODEL_VOLUME=${UAT_OLLAMA_MODEL_VOLUME}" "${identity_file}"; then
    echo "ERROR: The UAT worktree identity does not match the approved candidate SHA." >&2
    exit 1
fi

uat_compose up -d --build docker

for _ in $(seq 1 60); do
    if docker exec llm-stack-uat-docker docker info >/dev/null 2>&1; then
        break
    fi
    sleep 1
done
docker exec llm-stack-uat-docker docker info >/dev/null

if [[ -n "$(docker exec llm-stack-uat-docker docker container ls --all --quiet)" ]]; then
    echo "ERROR: The UAT image cache still contains containers from an earlier run." >&2
    echo "Run make uat-destroy for that run before starting a new one." >&2
    exit 1
fi
if [[ -n "$(docker exec llm-stack-uat-docker docker volume ls --quiet)" ]]; then
    echo "ERROR: The UAT image cache still contains application volumes from an earlier run." >&2
    echo "Run make uat-destroy for that run before starting a new one." >&2
    exit 1
fi

set +e
docker exec --workdir "${UAT_WORKTREE}" llm-stack-uat-docker ./start.sh "$@"
start_status=$?
set -e

# Return generated worktree files to the operator without changing Vault Agent
# secret ownership. Symlinks are skipped so this cannot chown outside the UAT tree.
docker exec -u 0 llm-stack-uat-docker find "${UAT_WORKTREE}" \
    \( -path "${UAT_WORKTREE}/vault/secrets_ram" -o -type l \) -prune -o \
    -exec chown "$(id -u):$(id -g)" {} +

if (( start_status != 0 )); then
    exit "${start_status}"
fi

# Catch bind-mount ownership regressions before UAT smoke tests. The Vault
# Agent runs unprivileged and must retain access to its rendered account file.
docker exec --workdir "${UAT_WORKTREE}" llm-stack-uat-docker \
    docker compose exec -T vault-agent sh -ec 'test -r /run/secrets/authentik.env'

echo "UAT stack started inside the isolated Docker daemon."
