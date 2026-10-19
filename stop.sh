#!/usr/bin/env bash
# ==============================================================================
# LLM Stack - Service Shutdown Script
# Stops all containers gracefully while preserving persistent Docker volumes.
# ==============================================================================

set -e

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

echo "🛑 Stopping LLM Stack containers..."
docker compose down

echo "✅ All LLM Stack containers stopped (volumes preserved)."
