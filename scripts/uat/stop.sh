#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

if uat_compose ps --status running --services | grep -qx docker; then
    docker exec --workdir "${UAT_WORKTREE}" llm-stack-uat-docker docker compose down
fi

uat_compose stop docker
echo "UAT stopped. Run make uat-destroy with CAB approval to remove this disposable run."
