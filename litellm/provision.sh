#!/usr/bin/env bash
# ==============================================================================
# LiteLLM - Seed the Admin SSO Login
# Called by ../start.sh after Authentik reconciliation and the LiteLLM and
# PostgreSQL readiness gates.
#
# The actual proxy_admin role assignment is no longer done here: it's now handled natively by
# Authentik on every LiteLLM login via the GENERIC_USER_ROLE_ATTRIBUTE mapping (see
# authentik/blueprints/20-native-oidc.yaml and docker-compose.yml). This script only
# pre-warms the admin's LiteLLM_UserTable row with a real SSO login, so it exists
# immediately after ./start.sh rather than only after someone's first manual visit.
#
# The actual Python logic lives in litellm/scripts/provision.py (extracted from an inline
# `python3 -c "..."` heredoc so it can be linted/read/tested like normal Python) - this script
# is a thin bash orchestrator that calls that script.
#
# Requires DOMAIN and UI_PASSWORD to be set in the environment (exported by
# start.sh from .env), and must be run from the repo root (docker compose
# context).
# ==============================================================================

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR" || exit 1

echo "Seeding the admin's LiteLLM SSO login (proxy_admin role now assigned natively by Authentik)..."
python3 "$REPO_DIR/litellm/scripts/provision.py"
