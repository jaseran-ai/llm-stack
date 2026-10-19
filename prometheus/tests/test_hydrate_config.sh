#!/usr/bin/env bash
# Verify Prometheus hydration requires and substitutes the Vault-rendered Qdrant key.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
test_dir="$(mktemp -d)"
trap 'rm -rf "${test_dir}"' EXIT

mkdir -p "${test_dir}/prometheus" "${test_dir}/vault/secrets_ram"
cp "${REPO_DIR}/prometheus/prometheus.yml.template" "${test_dir}/prometheus/prometheus.yml.template"
printf 'QDRANT__SERVICE__API_KEY=test-qdrant-key\n' >"${test_dir}/vault/secrets_ram/qdrant.env"

"${REPO_DIR}/prometheus/scripts/hydrate_config.sh" "${test_dir}"
grep -Fq "secrets: ['test-qdrant-key']" "${test_dir}/prometheus/prometheus.yml"
! grep -Fq '${QDRANT_API_KEY}' "${test_dir}/prometheus/prometheus.yml"
test "$(stat -c '%a' "${test_dir}/prometheus/prometheus.yml")" = "644"

printf '' >"${test_dir}/vault/secrets_ram/qdrant.env"
if "${REPO_DIR}/prometheus/scripts/hydrate_config.sh" "${test_dir}"; then
    echo "Expected hydration to reject a missing Qdrant key." >&2
    exit 1
fi
