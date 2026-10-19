# Ollama - Bundled CPU-Only Inference Backend

This folder documents the `ollama` Docker service: the **only** inference backend in this
stack, running entirely **inside** the Docker Compose project (no external machine, no GPU).
Every model declared in [`../litellm/litellm-config.yaml`](../litellm/litellm-config.yaml) is an
alias of this single weight. The stack used to depend on `llama-server`, a GPU inference backend
running on a separate physical machine; that dependency has been **fully removed**, so a fresh
clone always has real, working LLMs immediately after `docker compose up -d`, on any machine,
with zero external hardware.

---

## Files

| File | Role | Tracked in Git |
| :--- | :--- | :--- |
| `provision.sh` | Pulls the model weight (`ollama pull`). Idempotent, called by `../init.sh` right after `docker compose up -d`. | Yes |

The model weights themselves live in the `ollama_data` named Docker volume (`/root/.ollama`
inside the container) — never in Git.

---

## Model Choice: `lfm2.5-thinking:1.2b`

[Liquid AI's LFM2.5](https://ollama.com/library/lfm2.5-thinking), `1.2B` parameters, `Q4_K_M`
quantization, **~731MB** download. Chosen specifically because:

* **No GPU required.** Small enough to generate a real completion on any modern CPU in a
  reasonable time (~10 tokens/sec on a modest 4-core CPU once threads are pinned correctly -
  see "CPU Thread Pinning" below for a real bug this uncovered).
* **128K context window** (`details.context_length` from `/api/tags`) despite the tiny size.
* **Native "thinking"/reasoning support** (`capabilities: ["completion", "tools", "thinking"]`),
  with a native API-level toggle (`think: true/false`) - see below.
* **Multilingual.**

This single weight is aliased in LiteLLM (see
[`../litellm/README.md`](../litellm/README.md) for the full table): `lfm2.5-thinking-1.2b`
(general/default) and `lfm2.5-thinking-1.2b-no-think` (thinking disabled). Ollama only ever
loads the weight once regardless of how many LiteLLM aliases point to it.

---

## CPU Thread Pinning (a Real ~15x Performance Bug)

Without any explicit thread configuration, generation measured at only **~0.6 tokens/sec** on
a 4-core sandbox host - roughly 15-50x slower than expected for a 1.2B Q4 model on this class of
CPU. This was tracked down to a real, reproducible root cause, not just "the machine is slow":

* `nproc` inside the `ollama` container correctly reports the real, cgroup-constrained core
  count (4), but `llama-server` (Ollama's inference backend) was still spawning far more
  simultaneously-runnable compute threads than that (confirmed via
  `/proc/<pid>/task/*/status`: 6 threads in the `R (running)` state at once, out of ~15-20
  total OS threads).
* This produced a very high context-switch rate (confirmed via `vmstat`: ~15,000-20,000
  context switches/sec, versus a few hundred expected for a well-behaved 4-thread compute
  workload on 4 cores) - directly hurting the CPU-cache locality that matrix-multiplication-heavy
  LLM inference depends on.
* Explicitly pinning the thread count to the real core count fixed this completely: verified
  at **~9-10 tokens/sec** afterwards (through the full LiteLLM pipeline, cold-load included) -
  roughly a **15x improvement**, with no other change.

`ollama/provision.sh` fixes this unconditionally (not as a one-off workaround): after pulling
the model, it re-creates the same `lfm2.5-thinking:1.2b` tag with `PARAMETER num_thread <N>`
baked in, where `<N>` is dynamically read from `docker compose exec ollama nproc` (never
hardcoded) - so it always matches whatever machine the stack is actually deployed on. Explicitly
pinning the thread count this way is never worse than, and can be dramatically better than,
relying on auto-detection, so this is applied as a general hardening measure rather than a
workaround for one specific environment. The pull-then-recreate step is repeated idempotently on
every `init.sh` run (Ollama's `pull` re-syncs the tag with the upstream registry version first,
which strips the custom parameter layer - `provision.sh` immediately re-applies it afterwards).

---

## Why the Docker Service Has No GPU Reservation

The `ollama` service in [`../docker-compose.yml`](../docker-compose.yml) intentionally has **no**
`deploy.resources.reservations.devices` GPU block. Ollama auto-detects and uses a GPU if one is
actually available and exposed to the container, but nothing in the service definition requires
it — the whole point is that this works identically on a laptop with no GPU at all.

---

## Healthcheck: No curl/wget in the Image

The official `ollama/ollama` image ships **neither `curl` nor `wget`** (confirmed empirically:
`which curl wget` returns nothing inside the container) — only `bash`. The healthcheck therefore
uses `/dev/tcp` (a bash builtin) to issue a real HTTP request with zero external dependency, the
same pattern already used for Qdrant's healthcheck:

```yaml
test: ["CMD", "bash", "-c", "exec 3<>/dev/tcp/localhost/11434; printf 'GET / HTTP/1.0\r\n\r\n' >&3; grep -q '200 OK' <&3"]
```

A plain `wget --spider ...` healthcheck (the first attempt) silently failed every single probe
with `exec: "wget": executable file not found in $PATH`, leaving the container stuck at
`health: starting` forever.

---

## LiteLLM Integration

Wired into [`../litellm/litellm-config.yaml`](../litellm/litellm-config.yaml) using LiteLLM's
`ollama_chat/` provider prefix (recommended by LiteLLM over the plain `ollama/` prefix) pointed at
`http://ollama:11434` — no API key needed (Ollama has no built-in auth).

### Reasoning / "Thinking" Trace

Ollama's native `/api/chat` returns the reasoning trace in a **separate field**,
`message.thinking`, distinct from the final answer in `message.content`, toggled via a native
`think: true/false` request field (see [Ollama's thinking docs](https://docs.ollama.com/capabilities/thinking)).

Confirmed empirically that LiteLLM automatically maps `message.thinking` to the OpenAI-style
`message.reasoning_content` field, and correctly forwards the `think` field through to Ollama:

```bash
# think enabled (default) -> reasoning_content populated, content empty until the model
# finishes "thinking"
curl https://litellm.${DOMAIN}/v1/chat/completions \
  -H "Authorization: Bearer ${LITELLM_MASTER_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"model": "lfm2.5-thinking-1.2b", "messages": [{"role": "user", "content": "Say hi"}], "max_tokens": 20}'
# -> { "choices": [{ "message": {
#        "content": "",
#        "reasoning_content": "Okay, let's see. The user said \"Say hi\". I need to respond"
#      }}] }

# think: false -> no split: the model's raw output, including the literal, unparsed
# "<think>...</think>" tag, is returned as-is in content
curl https://litellm.${DOMAIN}/v1/chat/completions \
  -H "Authorization: Bearer ${LITELLM_MASTER_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"model": "lfm2.5-thinking-1.2b-no-think", "messages": [{"role": "user", "content": "Say hi"}], "max_tokens": 20}'
# -> { "choices": [{ "message": {
#        "content": "<think> Okay, let's see. The user said \"Say hi\". I need to respond"
#      }}] }
```

Open WebUI renders `reasoning_content` as its usual collapsible "thinking" block in the chat UI,
same as any other reasoning model.

**Important caveat**: `think: false` does not make the model skip reasoning or answer faster —
it only changes whether Ollama splits the trace out of `content`. The underlying model still
"thinks" the same amount either way (confirmed empirically: both variants produced the identical
reasoning text for the same prompt, just structured differently in the response).

---

## Unbounded Generation Risk (No Natural Stop for a Small Hybrid-Reasoning Model)

`lfm2.5-thinking:1.2b` is a small "hybrid thinking" model: for open-ended or context-heavy
prompts (for example, Open WebUI's web search or RAG flows, which inject a lot of retrieved text
into the prompt) it can keep reasoning far longer than a larger, better-aligned model would,
with no natural stopping point. Confirmed empirically: a single test completion (web search
prompt, no `max_tokens` set) ran past 1000 tokens and 20+ minutes on a CPU-throttled sandbox
without reaching a final answer.

Two mitigations are applied:

1. **`max_tokens` set on the model itself** (`open-webui/provision.sh`'s `knowledge-search-assistant`
   preset sets `params.max_tokens: 300`), so every completion using that model is bounded
   regardless of what the caller passes — Open WebUI's own internal/background completions using
   the same model are bounded too, not just the user-facing one.
2. **Open WebUI's auxiliary background generation tasks are disabled** (`task.title.enable`,
   `task.tags.enable`, `task.follow_up.enable`, `task.query.search.enable`,
   `task.query.retrieval.enable`) — each of these normally triggers an *additional*, separate LLM
   call per user message (title generation, tag generation, follow-up suggestions, and crucially
   a query-rewrite call *before* web search even runs), none of which respect the client's or the
   model's own `max_tokens` setting the same way. Disabling them removes several redundant,
   unbounded CPU-bound calls per message.

---

## Open WebUI Default Model

`DEFAULT_MODELS=lfm2.5-thinking-1.2b` is set on the `open-webui` service in
[`../docker-compose.yml`](../docker-compose.yml), making it the pre-selected model for every new
chat.

**Important**: Open WebUI only *seeds* this as a default on a fresh install — its
`ui.default_models` config key, once written to `webui.db` (even as `null`), takes precedence
over the `DEFAULT_MODELS` environment variable on every subsequent restart
(`Config.seed_defaults()` only inserts keys that do not already exist in the database). This is
by design: it lets an admin permanently change the default from the UI without the env var
fighting back on every restart. Confirmed empirically against a live instance:

```
DEFAULT_MODELS not read at all once ui.default_models already exists in webui.db
  -> only takes effect on the very first startup (empty webui.db), i.e. genuinely fresh clones.
```

---

## Provisioning (`provision.sh`)

Called by `../init.sh` right after `docker compose up -d` (needs the container actually running,
unlike `../grafana/provision.sh`, which is pure file/DB manipulation
run *before* `up -d`). Runs `docker compose exec ollama ollama pull lfm2.5-thinking:1.2b`, which
is idempotent — a fast no-op re-verifying the manifest/digest if the model is already present.
Placed first among the post-startup provisioning steps in `init.sh` since it is the
longest-running one on a truly fresh clone (~731MB download).

---

## Smoke Test

`smoke_test.sh`'s `test_ollama_default_model` calls `lfm2.5-thinking-1.2b` through LiteLLM with a
small `max_tokens` and asserts a non-empty `content`/`reasoning_content`. Every other model-backed
test in the suite (`test_open_webui`, the Open WebUI RAG and web
search tests) also runs against this same bundled model, now that `llama-server` has been
removed — the whole suite is CPU-only and has no external hardware dependency.
