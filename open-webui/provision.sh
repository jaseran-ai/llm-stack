#!/usr/bin/env bash
# ==============================================================================
# Open WebUI - Web Search Fix, RBAC Fix, Knowledge Base & Model Provisioning
# Called by ../start.sh after Open WebUI, LiteLLM, and Qdrant are ready.
#
# Authentication note: Open WebUI is configured with WEBUI_AUTH_TRUSTED_EMAIL_HEADER
# (see docker-compose.yml), the same "X-Authentik-Email" header Authentik's
# forward-auth outpost passes through Traefik for real users (Open WebUI sits
# behind that outpost -
# see ../authentik/README.md). Calling /api/v1/auths/signin directly
# against the container's mapped port with that header set logs us in as the admin without
# ever needing to know a password - simpler than the OIDC dance used by the
# Langfuse/LiteLLM provisioning scripts, because Open WebUI has this native
# trusted-header shortcut and they don't.
#
# Requires OPEN_WEBUI_PORT to be set in the environment (exported by start.sh
# from .env), and must be run from the repo root (relative path to the example
# PDF file).
#
# The actual Python logic lives in open-webui/scripts/provision.py (extracted from an inline
# `python3 -c "..."` heredoc so it can be linted/read/tested like normal Python) - this script
# is a thin bash orchestrator: env defaults and calling that script.
# ==============================================================================

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR" || exit 1

echo "Provisioning Open WebUI (web search fix, RBAC fix, knowledge base, model)..."
OPEN_WEBUI_PORT="${OPEN_WEBUI_PORT:-8080}" PDF_PATH="$REPO_DIR/open-webui/aapl-20260627.pdf" \
  python3 "$REPO_DIR/open-webui/scripts/provision.py"
