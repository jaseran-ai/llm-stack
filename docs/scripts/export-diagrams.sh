#!/usr/bin/env bash
# ==============================================================================
# LLM Stack — Automated Vector Diagram Generator
# Exports Structurizr C4 DSL and Mermaid sources to SVG in isolated containers
# ==============================================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
C4_DIR="$ROOT_DIR/docs/architecture/docs/c4"
DIAGRAMS_DIR="$ROOT_DIR/docs/architecture/docs/diagrams"

echo "==> [1/3] Validating & exporting Structurizr C4 DSL model..."
mkdir -p "$C4_DIR/svg"
docker run --rm \
  -v "$C4_DIR":/workspace \
  structurizr/cli:2025.11.09@sha256:0399ac8e24c16e41277cfcec22caa29e4775013e5395c0720016828426d62749 \
  validate -w /workspace/workspace.dsl

docker run --rm \
  -v "$C4_DIR":/workspace \
  structurizr/cli:2025.11.09@sha256:0399ac8e24c16e41277cfcec22caa29e4775013e5395c0720016828426d62749 \
  export -w /workspace/workspace.dsl -f mermaid -o /workspace/svg/

echo "==> [2/3] Compiling C4 Mermaid files to vector SVG..."
for mmd in "$C4_DIR"/svg/*.mmd; do
  if [ -f "$mmd" ]; then
    base="$(basename "$mmd" .mmd)"
    echo "  Compiling C4 $base.mmd -> $base.svg"
    docker run --rm --user "$(id -u):$(id -g)" \
      -v "$C4_DIR/svg":/workspace \
      minlag/mermaid-cli:11.4.2@sha256:99c983b3ab4e14033f2880bc1b9de17e5090b4515dabd63fe9cf8c0ae6130956 \
      -i "/workspace/$base.mmd" -o "/workspace/$base.svg" -b transparent
  fi
done

echo "==> [3/3] Compiling standalone Mermaid diagrams to SVG..."
mkdir -p "$DIAGRAMS_DIR/svg" "$DIAGRAMS_DIR/src"
for mmd in "$DIAGRAMS_DIR"/src/*.mmd; do
  if [ -f "$mmd" ]; then
    base="$(basename "$mmd" .mmd)"
    echo "  Compiling Sequence $base.mmd -> $base.svg"
    docker run --rm --user "$(id -u):$(id -g)" \
      -v "$DIAGRAMS_DIR":/workspace \
      minlag/mermaid-cli:11.4.2@sha256:99c983b3ab4e14033f2880bc1b9de17e5090b4515dabd63fe9cf8c0ae6130956 \
      -i "/workspace/src/$base.mmd" -o "/workspace/svg/$base.svg" -b transparent
  fi
done

echo "PASS: All architectural vector diagrams successfully exported."
