#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=common.sh
source "${SCRIPT_DIR}/common.sh"

identity_file="${UAT_WORKTREE}/.uat-identity"
if [[ ! -f "${identity_file}" ]] || ! grep -qx "CANDIDATE_SHA=${UAT_CANDIDATE_SHA}" "${identity_file}" || ! grep -qx "RUN_ID=${UAT_RUN_ID}" "${identity_file}" || ! grep -qx "DOCKER_CACHE_VOLUME=${UAT_DOCKER_CACHE_VOLUME}" "${identity_file}" || ! grep -qx "OLLAMA_MODEL_VOLUME=${UAT_OLLAMA_MODEL_VOLUME}" "${identity_file}"; then
    echo "ERROR: Refusing to test an unidentified UAT candidate." >&2
    exit 1
fi

requested_keys=",${*// /,},"
requested_keys="${requested_keys^^}"
run_all=false
[[ "$#" -eq 0 ]] && run_all=true

inner_compose_exec() {
    # Variables in the single-quoted command expand inside the UAT Docker container.
    # shellcheck disable=SC2016
    uat_compose exec -T docker sh -ec \
        'cd "$1"; shift; exec docker compose exec -T "$@"' \
        sh "${UAT_WORKTREE}" "$@"
}

if [[ "${run_all}" == true || "${requested_keys}" == *",POSTGRES,"* ]]; then
    postgres_result="$(inner_compose_exec postgres \
        psql --username postgres --dbname postgres --tuples-only --no-align --command 'SELECT 1;' \
        | tr -d '[:space:]')"
    if [[ "${postgres_result}" != "1" ]]; then
        echo "ERROR: UAT PostgreSQL SELECT 1 returned an unexpected result." >&2
        exit 1
    fi
    export SMOKE_POSTGRES_PROBE="${postgres_result}"
fi

if [[ "${run_all}" == true || "${requested_keys}" == *",REDIS,"* ]]; then
    # REDIS_AUTH expands only inside the isolated Redis container.
    # shellcheck disable=SC2016
    redis_result="$(inner_compose_exec redis sh -ec \
        'REDISCLI_AUTH="$REDIS_AUTH" exec redis-cli --no-auth-warning ping' \
        | tr -d '\r\n')"
    if [[ "${redis_result}" != "PONG" ]]; then
        echo "ERROR: UAT Redis authenticated PING returned an unexpected result." >&2
        exit 1
    fi
    export SMOKE_REDIS_PROBE="${redis_result}"
fi

smoke_environment=()
[[ -v SMOKE_POSTGRES_PROBE ]] && smoke_environment+=(-e SMOKE_POSTGRES_PROBE)
[[ -v SMOKE_REDIS_PROBE ]] && smoke_environment+=(-e SMOKE_REDIS_PROBE)
uat_compose --profile smoke run --rm "${smoke_environment[@]}" smoke-test "$@"
