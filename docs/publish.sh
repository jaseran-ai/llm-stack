#!/usr/bin/env bash
# ==============================================================================
# LLM Stack — Documentation Site Publisher
# Builds, tests, and packages documentation site into an immutable container image
# ==============================================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ $# -lt 1 ]; then
  echo "Usage: $0 [user|architecture]"
  exit 1
fi

SITE="$1"

if [ "$SITE" != "user" ] && [ "$SITE" != "architecture" ]; then
  echo "Error: SITE must be either 'user' or 'architecture' (received: '$SITE')"
  exit 1
fi

GIT_COMMIT="$(git rev-parse --short HEAD 2>/dev/null || echo "uncommitted")"
IMAGE_TAG="llm-stack-docs-${SITE}:${GIT_COMMIT}"
LOCAL_TAG="llm-stack-docs-${SITE}:local"

SERVICE_NAME="docs-user-build"
if [ "$SITE" = "architecture" ]; then
  SERVICE_NAME="docs-arch-build"
fi

echo "==> Building ${SITE} documentation site in strict mode..."
docker compose -f "${ROOT_DIR}/docs/compose.yaml" run --rm "${SERVICE_NAME}"

echo "==> Packaging ${SITE} documentation into container image: ${IMAGE_TAG} (${LOCAL_TAG})..."
docker build \
  -f "${ROOT_DIR}/docs/Dockerfile.publish" \
  --build-arg SITE_DIR="docs/${SITE}" \
  -t "${IMAGE_TAG}" \
  -t "${LOCAL_TAG}" \
  "${ROOT_DIR}"

echo "=============================================================================="
echo "SUCCESS: Documentation image created: ${IMAGE_TAG} (tagged as ${LOCAL_TAG})"
echo "GitOps Deployment Directive:"
if [ "$SITE" = "architecture" ]; then
  echo "  Classification: PRIVATE (Strictly private internal network, no public ingress)"
else
  echo "  Classification: PUBLIC (Customer & Integrator documentation)"
fi
echo "  Image: ${IMAGE_TAG} / ${LOCAL_TAG}"
echo "=============================================================================="
