#!/usr/bin/env bash
# ==============================================================================
# Ollama - Default Model Pull
# Called by ../start.sh after the Ollama container has been created. Unlike
# Grafana's provisioner, this script needs a running container to talk to.
#
# Pulls LiquidAI/LFM2-1.2B-RAG (~730MB), the ONLY model weight in the stack -
# every entry in litellm/litellm-config.yaml is an alias or routing target
# of this same weight, and it is set as Open WebUI's DEFAULT_MODELS. It is
# deliberately small enough to run on any machine with no GPU, so the stack
# has real, working LLMs immediately after a fresh clone, with zero external
# hardware dependency.
#
# The pull is idempotent: "ollama pull" is a fast no-op (only re-verifies the
# manifest/digest) if the model is already present - safe to re-run on every
# start.sh invocation. See https://huggingface.co/LiquidAI/LFM2-1.2B-RAG
# ==============================================================================

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR" || exit 1

OLLAMA_SOURCE_MODEL="hf.co/LiquidAI/LFM2-1.2B-RAG-GGUF:Q4_K_M"
OLLAMA_MODEL="lfm2-1.2b-rag"

echo "Pulling the Ollama default model (${OLLAMA_SOURCE_MODEL}, ~730MB, first run only)..."

# Wait for the ollama container's healthcheck to pass (may still be starting right after
# "docker compose up -d").
for _ in $(seq 1 30); do
  status="$(docker inspect --format '{{.State.Health.Status}}' ollama 2>/dev/null)"
  [ "$status" = "healthy" ] && break
  sleep 2
done

if docker compose exec -T ollama ollama pull "$OLLAMA_SOURCE_MODEL"; then
  echo "   -> ${OLLAMA_SOURCE_MODEL} pulled successfully."
else
  echo "   -> WARNING: could not pull ${OLLAMA_SOURCE_MODEL}, re-run manually if needed:"
  echo "      docker compose exec ollama ollama pull ${OLLAMA_SOURCE_MODEL}"
fi

# Pin the number of CPU threads to the container's actual, real core count, instead of
# relying on Ollama/llama.cpp's own auto-detection.
#
# Confirmed empirically on a nested-virtualization sandbox: without this, generation ran at
# ~0.6 tokens/sec (a 4096-token context, 1.2B Q4 model on a 4-core host should be an order of
# magnitude faster). Root cause, confirmed via /proc/<pid>/task/*/status: llama-server was
# spawning 6 simultaneous RUNNING compute threads while the container's own cgroup only
# allows scheduling on 4 CPUs (`nproc` correctly reports 4, matching cpuset.cpus.effective) -
# a ~20000/sec context-switch rate (vmstat) on a cache-sensitive matmul workload, consistent
# with the observed ~10x slowdown. Re-creating the model with `PARAMETER num_thread <nproc>`
# baked in (below) fixed this completely: verified at ~10 tokens/sec afterwards, a ~15x
# improvement, through the full LiteLLM pipeline.
#
# This is applied unconditionally (not just as a workaround for pathological environments):
# explicitly pinning the thread count to the container's real core count is never worse than,
# and sometimes dramatically better than, auto-detection - so this is a general hardening, not
# a environment-specific hack. See ollama/README.md for the full investigation.
CPU_COUNT="$(docker compose exec -T ollama nproc 2>/dev/null | tr -d '[:space:]')" || true
if [ -n "$CPU_COUNT" ] && [ "$CPU_COUNT" -gt 0 ] 2>/dev/null; then
  echo "Pinning ${OLLAMA_MODEL} to ${CPU_COUNT} CPU threads (matches the container's real core count)..."
  docker compose exec -T ollama sh -c "printf 'FROM %s\nPARAMETER num_thread %s\n' '$OLLAMA_SOURCE_MODEL' '$CPU_COUNT' > /tmp/Modelfile.llm-stack"
  if docker compose exec -T ollama ollama create "$OLLAMA_MODEL" -f /tmp/Modelfile.llm-stack >/dev/null 2>&1; then
    echo "   -> num_thread=${CPU_COUNT} applied to ${OLLAMA_MODEL}."
  else
    echo "   -> WARNING: could not apply num_thread, ${OLLAMA_MODEL} will use Ollama's own auto-detected thread count."
    docker compose exec -T ollama ollama cp "$OLLAMA_SOURCE_MODEL" "$OLLAMA_MODEL" || true
  fi
else
  echo "   -> WARNING: could not detect the ollama container's CPU count, copying source model directly."
  docker compose exec -T ollama ollama cp "$OLLAMA_SOURCE_MODEL" "$OLLAMA_MODEL" || true
fi
