#!/usr/bin/env bash
# Render the Prometheus runtime configuration after Vault Agent provides Qdrant credentials.
set -euo pipefail

REPO_DIR="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
template_file="${REPO_DIR}/prometheus/prometheus.yml.template"
output_file="${REPO_DIR}/prometheus/prometheus.yml"
secret_file="${REPO_DIR}/vault/secrets_ram/qdrant.env"

if [[ ! -f "${secret_file}" ]]; then
    echo "ERROR: Qdrant runtime secret is not available at ${secret_file}." >&2
    exit 1
fi

qdrant_api_key="$(sed -n 's/^QDRANT__SERVICE__API_KEY=//p' "${secret_file}")"
if [[ -z "${qdrant_api_key}" ]]; then
    echo "ERROR: QDRANT__SERVICE__API_KEY is missing from ${secret_file}." >&2
    exit 1
fi

temporary_file="$(mktemp "${output_file}.XXXXXX")"
trap 'rm -f "${temporary_file}"' EXIT

sed "s|\${QDRANT_API_KEY}|${qdrant_api_key}|g" "${template_file}" >"${temporary_file}"
if grep -Fq '${QDRANT_API_KEY}' "${temporary_file}"; then
    echo "ERROR: Prometheus configuration still contains an unresolved Qdrant key placeholder." >&2
    exit 1
fi
chmod 644 "${temporary_file}"

mv "${temporary_file}" "${output_file}"
trap - EXIT
