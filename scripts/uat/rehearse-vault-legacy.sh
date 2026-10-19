#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

require_uat_run
"${SCRIPT_DIR}/preflight.sh"

identity_file="${UAT_WORKTREE}/.uat-identity"
if [[ ! -f "${identity_file}" ]] || ! grep -qx "ENVIRONMENT=uat" "${identity_file}" || \
    ! grep -qx "CANDIDATE_SHA=${UAT_CANDIDATE_SHA}" "${identity_file}" || \
    ! grep -qx "RUN_ID=${UAT_RUN_ID}" "${identity_file}"; then
    echo "ERROR: The disposable UAT identity does not match the approved candidate." >&2
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
set +e
docker exec --env PYTHONDONTWRITEBYTECODE=1 --workdir "${UAT_WORKTREE}" llm-stack-uat-docker \
    python3 vault/tests/rehearse_migration.py
rehearsal_status=$?
set -e

# The DinD controller runs as root. Return generated fixture ownership to the
# operator even on failure, while leaving the RAM symlink and target untouched.
docker exec -u 0 llm-stack-uat-docker find "${UAT_WORKTREE}" \
    \( -path "${UAT_WORKTREE}/vault/secrets_ram" -o -type l \) -prune -o \
    -exec chown "$(id -u):$(id -g)" {} +

exit "${rehearsal_status}"
