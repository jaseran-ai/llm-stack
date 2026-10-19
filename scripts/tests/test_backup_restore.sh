#!/usr/bin/env bash
# Unit tests for Backup/Restore validation and destructive-operation guards.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TMP_DIR="$(mktemp -d -t llm_stack_backup_tests_XXXXXX)"
PASSPHRASE="test-only-passphrase-123456"

cleanup() {
    rm -rf -- "${TMP_DIR}"
}
trap cleanup EXIT

assert_fails() {
    local description="$1"
    shift
    if "$@" >"${TMP_DIR}/stdout" 2>"${TMP_DIR}/stderr"; then
        echo "FAIL: ${description}" >&2
        exit 1
    fi
    echo "PASS: ${description}"
}

"${REPO_ROOT}/backup.sh" --help >/dev/null
"${REPO_ROOT}/restore.sh" --help >/dev/null
echo "PASS: compatibility entry points expose canonical help"

grep -q 'BACKUP_PASSPHRASE) openssl rand -hex 32' "${REPO_ROOT}/setup.sh"
grep -q '^    BACKUP_PASSPHRASE$' "${REPO_ROOT}/setup.sh"
grep -q '^BACKUP_PASSPHRASE=' "${REPO_ROOT}/.env.example"
echo "PASS: setup generates the required backup passphrase"

assert_fails "invalid backup consistency is rejected before runtime access" \
    env BACKUP_PASSPHRASE="${PASSPHRASE}" "${REPO_ROOT}/scripts/backup.sh" --consistency invalid
grep -q 'must be online or offline' "${TMP_DIR}/stderr"

touch "${TMP_DIR}/missing-checksum.tar.gz.enc"
assert_fails "restore requires an external checksum" \
    env BACKUP_PASSPHRASE="${PASSPHRASE}" "${REPO_ROOT}/scripts/restore.sh" \
        --archive "${TMP_DIR}/missing-checksum.tar.gz.enc" --component configs
grep -q 'Required checksum is missing' "${TMP_DIR}/stderr"

printf 'not-an-archive' > "${TMP_DIR}/guard.tar.gz.enc"
(
    cd "${TMP_DIR}"
    sha256sum guard.tar.gz.enc > guard.tar.gz.enc.sha256
)
assert_fails "a PostgreSQL restore requires explicit LiteLLM approval" \
    env BACKUP_PASSPHRASE="${PASSPHRASE}" "${REPO_ROOT}/scripts/restore.sh" \
        --archive "${TMP_DIR}/guard.tar.gz.enc" --component postgres
grep -q 'Explicit --allow-litellm-restart is required' "${TMP_DIR}/stderr"

mkdir -p "${TMP_DIR}/payload"
cat > "${TMP_DIR}/payload/manifest.env" <<'EOF'
FORMAT_VERSION=2
CREATED_AT=2026-08-29T00:00:00Z
CONSISTENCY=offline
PROJECT=llm-stack
EOF
(
    cd "${TMP_DIR}/payload"
    sha256sum manifest.env > files.sha256
)
tar -czf - -C "${TMP_DIR}/payload" . | \
    openssl enc -aes-256-cbc -salt -pbkdf2 -iter 200000 -md sha256 \
        -out "${TMP_DIR}/incomplete.tar.gz.enc" -pass fd:3 3<<<"${PASSPHRASE}"
(
    cd "${TMP_DIR}"
    sha256sum incomplete.tar.gz.enc > incomplete.tar.gz.enc.sha256
)
assert_fails "manifest validation rejects an incomplete payload before data changes" \
    env BACKUP_PASSPHRASE="${PASSPHRASE}" "${REPO_ROOT}/scripts/restore.sh" \
        --archive "${TMP_DIR}/incomplete.tar.gz.enc" --component configs \
        --confirm incomplete.tar.gz.enc
grep -q 'Required payload is missing' "${TMP_DIR}/stderr"

cp "${TMP_DIR}/incomplete.tar.gz.enc" "${TMP_DIR}/tampered.tar.gz.enc"
printf 'tamper' >> "${TMP_DIR}/tampered.tar.gz.enc"
cp "${TMP_DIR}/incomplete.tar.gz.enc.sha256" "${TMP_DIR}/tampered.tar.gz.enc.sha256"
sed -i 's/incomplete/tampered/' "${TMP_DIR}/tampered.tar.gz.enc.sha256"
assert_fails "checksum validation rejects a modified archive" \
    env BACKUP_PASSPHRASE="${PASSPHRASE}" "${REPO_ROOT}/scripts/restore.sh" \
        --archive "${TMP_DIR}/tampered.tar.gz.enc" --component configs

echo "Backup/Restore tests passed."
