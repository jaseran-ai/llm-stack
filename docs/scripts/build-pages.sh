#!/usr/bin/env bash
# ==============================================================================
# LLM Stack — Unified Documentation Builder for GitHub Pages
# Compiles both User Guide and Architecture Specification into a single _site tree
# ==============================================================================
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_DIR"

OUTPUT_DIR="${1:-${REPO_DIR}/_site}"
REPO_NAME="${REPO_NAME:-llm-stack}"
PAGES_DOMAIN="${PAGES_DOMAIN:-jaseran-ai.github.io}"

USER_BASE_URL="/${REPO_NAME}/"
ARCH_BASE_URL="/${REPO_NAME}/architecture/"
SITE_URL="https://${PAGES_DOMAIN}"

echo "=============================================================================="
echo "Building LLM Stack Documentation for GitHub Pages"
echo "  Target Directory : ${OUTPUT_DIR}"
echo "  Site URL         : ${SITE_URL}"
echo "  User Base URL    : ${USER_BASE_URL}"
echo "  Arch Base URL    : ${ARCH_BASE_URL}"
echo "=============================================================================="

rm -rf "${OUTPUT_DIR}"
mkdir -p "${OUTPUT_DIR}/architecture"

# Build User Documentation
echo "==> Building User Guide (docs/user)..."
if command -v docker >/dev/null 2>&1; then
  docker run --rm \
    -v "${REPO_DIR}/docs/user:/app" \
    -w /app \
    -e DOCS_BASE_URL="${USER_BASE_URL}" \
    -e DOCS_URL="${SITE_URL}" \
    node:22-alpine@sha256:0a7108bf6c7bf5de370ffb1a3ed6be93d405b43ff159f681a8d18c0e2bc2e402 \
    sh -c "[ -f node_modules/.bin/docusaurus ] || npm ci; npm run build"
else
  DOCS_BASE_URL="${USER_BASE_URL}" DOCS_URL="${SITE_URL}" sh -c "cd '${REPO_DIR}/docs/user' && ([ -f node_modules/.bin/docusaurus ] || npm ci) && npm run build"
fi

# Build Architecture Documentation
echo "==> Building Architecture Specification (docs/architecture)..."
if command -v docker >/dev/null 2>&1; then
  docker run --rm \
    -v "${REPO_DIR}/docs/architecture:/app" \
    -v "${REPO_DIR}/docs/shared:/app/shared:ro" \
    -w /app \
    -e DOCS_BASE_URL="${ARCH_BASE_URL}" \
    -e DOCS_URL="${SITE_URL}" \
    node:22-alpine@sha256:0a7108bf6c7bf5de370ffb1a3ed6be93d405b43ff159f681a8d18c0e2bc2e402 \
    sh -c "[ -f node_modules/.bin/docusaurus ] || npm ci; npm run build"
else
  DOCS_BASE_URL="${ARCH_BASE_URL}" DOCS_URL="${SITE_URL}" sh -c "cd '${REPO_DIR}/docs/architecture' && ([ -f node_modules/.bin/docusaurus ] || npm ci) && npm run build"
fi

# Assemble unified static output
echo "==> Assembling static publication tree..."
cp -R "${REPO_DIR}/docs/user/build/." "${OUTPUT_DIR}/"
cp -R "${REPO_DIR}/docs/architecture/build/." "${OUTPUT_DIR}/architecture/"

# Create .nojekyll to ensure GitHub Pages serves underscore assets (_docusaurus, etc.)
touch "${OUTPUT_DIR}/.nojekyll"

echo "=============================================================================="
echo "SUCCESS: GitHub Pages static site assembled at ${OUTPUT_DIR}"
echo "=============================================================================="
