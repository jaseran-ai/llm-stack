#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

require_uat_run
require_uat_cache

if [[ "${UAT_WORKTREE}" != "${UAT_REPO_ROOT}/uat/runtime/worktree" ]]; then
    echo "ERROR: UAT_WORKTREE must be the isolated runtime worktree." >&2
    exit 1
fi

echo "Starting the isolated Docker daemon to erase disposable application state..."
uat_compose up -d docker
for _ in $(seq 1 60); do
    if docker exec llm-stack-uat-docker docker info >/dev/null 2>&1; then
        break
    fi
    sleep 1
done
docker exec llm-stack-uat-docker docker info >/dev/null

if [[ -f "${UAT_WORKTREE}/docker-compose.yml" ]]; then
    docker exec --workdir "${UAT_WORKTREE}" llm-stack-uat-docker \
        docker compose down --volumes --remove-orphans
fi

mapfile -t remaining_containers < <(docker exec llm-stack-uat-docker docker container ls --all --quiet)
if (( ${#remaining_containers[@]} > 0 )); then
    docker exec llm-stack-uat-docker docker container rm --force "${remaining_containers[@]}"
fi

mapfile -t remaining_volumes < <(docker exec llm-stack-uat-docker docker volume ls --quiet)
if (( ${#remaining_volumes[@]} > 0 )); then
    docker exec llm-stack-uat-docker docker volume rm --force "${remaining_volumes[@]}"
fi

if [[ -n "$(docker exec llm-stack-uat-docker docker container ls --all --quiet)" ]] || \
    [[ -n "$(docker exec llm-stack-uat-docker docker volume ls --quiet)" ]]; then
    echo "ERROR: Disposable UAT containers or application volumes remain." >&2
    exit 1
fi

if [[ "${UAT_CERTS_DIR}" != "${UAT_REPO_ROOT}/uat/runtime/certs" ]]; then
    echo "ERROR: Refusing to remove an unexpected UAT certificate directory." >&2
    exit 1
fi
if [[ -d "${UAT_CERTS_DIR}" ]]; then
    docker exec llm-stack-uat-docker find /certs -mindepth 1 -depth -delete
fi

uat_compose down

# Only the per-run tmpfs metadata is disposable here; image/model caches survive.
secrets_volume="llm-stack-uat-secrets-${UAT_RUN_ID}"
if docker volume inspect "${secrets_volume}" >/dev/null 2>&1; then
    docker volume rm "${secrets_volume}"
fi

if [[ -e "${UAT_WORKTREE}" ]]; then
    if git -C "${UAT_REPO_ROOT}" worktree list --porcelain | grep -Fxq "worktree ${UAT_WORKTREE}"; then
        git -C "${UAT_REPO_ROOT}" worktree remove --force "${UAT_WORKTREE}"
    else
        find "${UAT_WORKTREE}" -mindepth 1 -depth -delete
        rmdir "${UAT_WORKTREE}"
    fi
fi
git -C "${UAT_REPO_ROOT}" worktree prune
rm -f "${UAT_RUN_ENV_FILE}"

echo "Disposable UAT run ${UAT_RUN_ID} was destroyed."
echo "Docker image cache ${UAT_DOCKER_CACHE_VOLUME} was preserved."
echo "Ollama model cache ${UAT_OLLAMA_MODEL_VOLUME} was preserved."
