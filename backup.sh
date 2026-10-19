#!/usr/bin/env bash
# Compatibility entry point for the canonical encrypted backup implementation.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "${REPO_ROOT}/scripts/backup.sh" "$@"
