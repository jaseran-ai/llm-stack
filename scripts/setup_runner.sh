#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
RUNNER_DIR="${REPO_ROOT}/runner"

if [[ $# -lt 1 && -z "${RUNNER_TOKEN:-}" ]]; then
    echo "Usage: $0 <GITHUB_RUNNER_TOKEN>"
    exit 1
fi

TOKEN="${1:-${RUNNER_TOKEN}}"
RUNNER_NAME_VALUE="${RUNNER_NAME:-llm-stack-runner}"

echo "==> Materializing runner files on the Docker host and recreating the vanilla runner..."
RUNNER_TOKEN="${TOKEN}" RUNNER_NAME="${RUNNER_NAME_VALUE}" \
    docker compose -f "${RUNNER_DIR}/docker-compose.yml" up -d --force-recreate

if [[ ! -x /actions-runner/externals/node24/bin/node ]]; then
    echo "ERROR: Node 24 was not materialized for container jobs." >&2
    exit 1
fi

for _ in $(seq 1 30); do
    if docker exec gh-actions-runner test -x /actions-runner/externals/node24/bin/node 2>/dev/null; then
        echo "==> Runner Node 24 bridge is ready."
        break
    fi
    sleep 1
done
docker exec gh-actions-runner test -x /actions-runner/externals/node24/bin/node

echo "==> Runner started successfully."
