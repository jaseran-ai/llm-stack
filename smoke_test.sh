#!/usr/bin/env bash
# ==============================================================================
# LLM Stack - Smoke Test Suite Runner
# Delegates execution to scripts/smoke_test.py.
# Supports running specific tests via UPPERCASE keys (e.g. ./smoke_test.sh GRAFANA,LITELLM)
# or listing available tests with ./smoke_test.sh --list.
# ==============================================================================

set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

command -v python3 >/dev/null 2>&1 || { echo "Python3 is required."; exit 1; }

requested_keys=",${*// /,},"
requested_keys="${requested_keys^^}"
run_all=false
[[ "$#" -eq 0 ]] && run_all=true

if [[ "${run_all}" == true || "${requested_keys}" == *",POSTGRES,"* ]]; then
    postgres_result="$(docker compose exec -T postgres \
        psql --username postgres --dbname postgres --tuples-only --no-align --command 'SELECT 1;' \
        | tr -d '[:space:]')"
    if [[ "${postgres_result}" != "1" ]]; then
        echo "ERROR: PostgreSQL SELECT 1 returned an unexpected result." >&2
        exit 1
    fi
    export SMOKE_POSTGRES_PROBE="${postgres_result}"
fi

if [[ "${run_all}" == true || "${requested_keys}" == *",REDIS,"* ]]; then
    # REDIS_AUTH expands only inside the Redis container.
    # shellcheck disable=SC2016
    redis_result="$(docker compose exec -T redis sh -ec \
        'REDISCLI_AUTH="$REDIS_AUTH" exec redis-cli --no-auth-warning ping' \
        | tr -d '\r\n')"
    if [[ "${redis_result}" != "PONG" ]]; then
        echo "ERROR: Redis authenticated PING returned an unexpected result." >&2
        exit 1
    fi
    export SMOKE_REDIS_PROBE="${redis_result}"
fi

exec python3 "$REPO_DIR/scripts/smoke_test.py" "$@"
