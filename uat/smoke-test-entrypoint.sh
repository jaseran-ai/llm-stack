#!/bin/sh
set -eu

identity_file="${SMOKE_UAT_IDENTITY_FILE:?SMOKE_UAT_IDENTITY_FILE is required}"
expected_ip="${SMOKE_UAT_TRAEFIK_IP:?SMOKE_UAT_TRAEFIK_IP is required}"

if [ "${SMOKE_ENVIRONMENT:-}" != "uat" ]; then
    echo "ERROR: SMOKE_ENVIRONMENT must be uat." >&2
    exit 1
fi

if [ ! -f "$identity_file" ]; then
    echo "ERROR: UAT identity file not found: $identity_file" >&2
    exit 1
fi

environment="$(sed -n 's/^ENVIRONMENT=//p' "$identity_file")"
candidate_sha="$(sed -n 's/^CANDIDATE_SHA=//p' "$identity_file")"
if [ "$environment" != "uat" ] || [ -z "$candidate_sha" ]; then
    echo "ERROR: Invalid UAT identity file." >&2
    exit 1
fi

domain="$(sed -n 's/^DOMAIN=//p' .env)"
if [ -z "$domain" ]; then
    echo "ERROR: DOMAIN is missing from the isolated UAT .env." >&2
    exit 1
fi

hosts="$domain authentik.$domain chat.$domain grafana.$domain litellm.$domain langfuse.$domain logs.$domain searxng.$domain s3.$domain s3-console.$domain clickhouse.$domain qdrant.$domain status.$domain vault.$domain traefik.$domain alertmanager.$domain docs.$domain arch.$domain"
for host in $hosts; do
    resolved="$(getent ahostsv4 "$host" | awk 'NR == 1 { print $1 }')"
    if [ "$resolved" != "$expected_ip" ]; then
        echo "ERROR: $host resolves to $resolved, expected UAT target $expected_ip." >&2
        exit 1
    fi
done

echo "========================================================================"
echo " UAT TARGET VERIFICATION"
echo " Candidate SHA : $candidate_sha"
echo " Domain        : $domain"
echo " Traefik IP    : $expected_ip"
echo "========================================================================"

exec python3 scripts/smoke_test.py "$@"
