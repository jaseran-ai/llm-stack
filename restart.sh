#!/usr/bin/env bash
# ==============================================================================
# LLM Stack - Service Restart Script
# Gracefully restarts the entire stack via ./stop.sh and ./start.sh.
# ==============================================================================

set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

echo "🔄 Restarting LLM Stack..."
bash "$REPO_DIR/stop.sh"
sleep 2
bash "$REPO_DIR/start.sh" "$@"
