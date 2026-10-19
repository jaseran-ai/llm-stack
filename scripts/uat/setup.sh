#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

if [[ -e "${UAT_WORKTREE}" ]]; then
    echo "ERROR: UAT worktree already exists: ${UAT_WORKTREE}" >&2
    exit 1
fi
if [[ -e "${UAT_RUN_ENV_FILE}" ]]; then
    echo "ERROR: A disposable UAT run already exists. Run make uat-destroy before preparing another one." >&2
    exit 1
fi

run_id="$(date -u +%Y%m%d%H%M%S)-$(openssl rand -hex 4)"
mkdir -p "$(dirname "${UAT_RUN_ENV_FILE}")"
(
    umask 077
    {
        echo "UAT_RUN_ID=${run_id}"
        echo "UAT_WORKTREE_UID=$(id -u)"
        echo "UAT_WORKTREE_GID=$(id -g)"
        echo "UAT_SECRETS_RAM_ID=$(openssl rand -hex 8)"
    } > "${UAT_RUN_ENV_FILE}"
)
set -a
# shellcheck disable=SC1090
source "${UAT_RUN_ENV_FILE}"
set +a

"${SCRIPT_DIR}/preflight.sh"

mkdir -p "$(dirname "${UAT_WORKTREE}")"
git -C "${UAT_REPO_ROOT}" worktree add --detach "${UAT_WORKTREE}" "${UAT_CANDIDATE_SHA}"

# A shared Git index can mark this tracked extension point as assume-unchanged on
# the operator's checkout. Always materialize the candidate's committed version
# so private host endpoints and credentials cannot leak into isolated UAT.
candidate_models_tmp="${UAT_WORKTREE}/litellm/custom_models.yaml.candidate"
git -C "${UAT_REPO_ROOT}" show \
    "${UAT_CANDIDATE_SHA}:litellm/custom_models.yaml" > "${candidate_models_tmp}"
mv "${candidate_models_tmp}" "${UAT_WORKTREE}/litellm/custom_models.yaml"

# Keep model weights outside disposable inner Docker volumes. The fixed path is
# backed by the dedicated outer volume mounted into the DinD controller.
install -m 0644 \
    "${UAT_WORKTREE}/uat/ollama-model-cache.override.yml" \
    "${UAT_WORKTREE}/docker-compose.override.yml"

(
    cd "${UAT_WORKTREE}"
    SECRETS_RAM_ID="${UAT_SECRETS_RAM_ID}" DOMAIN="${UAT_DOMAIN}" TLS_MODE=internal COMPOSE_PROFILES="" ./setup.sh --domain="${UAT_DOMAIN}"
    {
        echo "ENVIRONMENT=uat"
        echo "CANDIDATE_SHA=${UAT_CANDIDATE_SHA}"
        echo "RUN_ID=${UAT_RUN_ID}"
        echo "DOCKER_CACHE_VOLUME=${UAT_DOCKER_CACHE_VOLUME}"
        echo "OLLAMA_MODEL_VOLUME=${UAT_OLLAMA_MODEL_VOLUME}"
    } > .uat-identity
)

echo "UAT candidate prepared at ${UAT_WORKTREE}."
echo "UAT run: ${UAT_RUN_ID}"
echo "UAT image cache: ${UAT_DOCKER_CACHE_VOLUME}"
echo "UAT Ollama model cache: ${UAT_OLLAMA_MODEL_VOLUME}"
echo "No container was started."
