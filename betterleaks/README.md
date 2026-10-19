# Betterleaks + Microsoft Presidio Unified Redaction Service

A high-performance, unified security microservice that merges **Betterleaks** (400+ rules, BPE token efficiency secrets detection) with **Microsoft Presidio** (PII detection and redaction engine).

---

## 🏛️ Architecture & Endpoints

The service exposes both standard Microsoft Presidio endpoints and a unified one-step redaction endpoint:

```text
                               ┌─────────────────────────────┐
                               │   Betterleaks + Presidio    │
                               │          Service            │
POST /redact ─────────────────►│                             │
                               │ 1. Presidio spaCy (PII)     │
                               │ 2. Betterleaks BPE (Secrets)│──► Clean, Redacted Text
                               │ 3. Presidio Anonymizer      │
                               └─────────────────────────────┘
```

| Endpoint | Method | Purpose |
| :--- | :--- | :--- |
| `/healthz` | `GET` | Health check probe (HTTP 200 `healthy`). |
| `/analyze` | `POST` | Standard Presidio analyzer endpoint (compatible with LiteLLM guardrail). |
| `/anonymize` | `POST` | Standard Presidio anonymizer endpoint. |
| `/redact` | `POST` | Unified one-step endpoint: detects both PII and secrets, returns clean text and findings. |
| `/tokenize` | `POST` | Ephemeral surrogate tokenization: replaces secrets with `TOK_<ENTITY>_<hex>`, caches mappings in Redis with TTL. |
| `/detokenize` | `POST` | Reversible rehydration: resolves surrogate tokens from Redis to restore credentials for authorized clients. |
| `/metrics` | `GET` | Prometheus telemetry metrics (`scans_total`, `findings_total`, `scan_duration_seconds`). |

---

## 🌐 Multilingual Support & False-Positive Prevention

The microservice includes native bilingual NLP engines and intelligent noise filtering tailored for developer chats and technical contexts:

1. **Bilingual spaCy NLP Models**:
   - Both `en_core_web_sm` (English) and `fr_core_news_sm` (French) are baked into the container.
   - Predefined Presidio recognizers (`EmailRecognizer`, `PhoneRecognizer`, `IbanRecognizer`, `CryptoRecognizer`, `IpRecognizer`, `SpacyRecognizer`) are registered for both languages.
   - The Betterleaks binary secret scanner (400+ rules) runs uniformly across all languages.

2. **Toggleable French Support (`ENABLE_FRENCH_SUPPORT`)**:
   - `ENABLE_FRENCH_SUPPORT=true` (default): loads French models and registers French recognizers.
   - `ENABLE_FRENCH_SUPPORT=false`: disables French models to run in lightweight English-only mode.

3. **Automatic Language Detection (`AUTO_DETECT_LANGUAGE`)**:
   - Requests with `language="auto"` (the default) automatically detect French vs. English via sub-millisecond accent analysis (diacritics) and stopword frequency.
   - You can also explicitly specify `"language": "fr"` or `"language": "en"`.

4. **False-Positive Elimination in Developer Chats**:
   - **Entity Filtering (`IGNORED_ENTITIES`)**: Noisy generic NLP entity categories (`ORGANIZATION`, `LOCATION`, `NRP`, `GPE`, `DATE_TIME`, `URL`) are ignored by default. In developer conversations, words like "un", "dans", "AWS", "Docker", "Paris", and documentation/repository links (`https://huggingface.co/...`) are never redacted as secrets or PII.
   - **Technical Dictionary & Code Identifier Heuristics for `PERSON`**: Prevents code variables, developer tools, platforms, VCS commands (`Git`, `repo Git`, `Docker`, `Python`, `HF_TOKEN`, `API_KEY`), and lowercase words from being misclassified as personal names. Real human names ("John Doe", "Alice", "Emmanuel Macron") remain protected.

5. **Open-WebUI Filter Valves**:
   - `language`: `"auto"`, `"en"`, or `"fr"`.
   - `enable_french`: toggle French language processing on/off directly from the Open-WebUI admin UI.
   - `ignored_entities`: comma-separated list of entities to skip (defaults to `"ORGANIZATION,LOCATION,NRP,GPE,DATE_TIME,URL"`).

---

## ⚙️ Betterleaks Configuration Guide (`config/betterleaks.toml`)

Rules and allowlists are declaratively configured in [`config/betterleaks.toml`](config/betterleaks.toml). The file is mounted into the running container as a read-only volume (`/app/config/betterleaks.toml:ro`), enabling instant updates without rebuilding the image.

### 1. File Structure & Inheritance

```toml
title = "llm-stack Betterleaks Security Configuration"

# Inherit all 417+ built-in community rules (AWS, GitHub, Slack, OpenAI, Private Keys, etc.)
[extend]
useDefault = true

[[rules]]
# Custom rules definition...

[allowlist]
# Global allowlist definition...
```

- When `[extend] useDefault = true` is set, Betterleaks combines your custom rules with all built-in rules.
- If set to `false`, Betterleaks will exclusively scan for the rules declared in this file.

---

### 2. Defining Custom Secret Rules (`[[rules]]`)

Each custom secret pattern is declared with a `[[rules]]` block.

#### Field Reference

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `id` | `string` | **Yes** | Unique identifier (lowercase, hyphenated, e.g. `vault-token`). Presidio automatically converts this to uppercase snake-case (`VAULT_TOKEN`). |
| `description` | `string` | **Yes** | Clear explanation of the credential type and risk. |
| `regex` | `string` | **Yes** | RE2 regular expression. Always enclose in triple single quotes (`'''...'''`) to avoid escaping backslashes. |
| `keywords` | `list[str]` | **Recommended** | Substring prefixes used by Betterleaks's fast pre-filter. Before evaluating the regex, Betterleaks checks if at least one keyword is present in the text. This gives Betterleaks sub-millisecond execution speeds. |
| `entropy` | `float` | No | Minimum Shannon entropy threshold (e.g. `3.5`). Filters out synthetic test strings or repeated patterns with insufficient randomness. |
| `confidence` | `string` | No | Confidence assessment: `low`, `medium`, or `high`. |
| `secret` | `string` | No | Capture group index (e.g. `"$1"`) if the regex captures surrounding context and only part of the match is the actual secret. |

#### Real Examples from `betterleaks.toml`

**Example A: HashiCorp Vault Token**
```toml
[[rules]]
id = "vault-token"
description = "Detected a HashiCorp Vault token"
regex = '''\b(hvb\.[a-zA-Z0-9_-]{24,}|hvs\.[a-zA-Z0-9_-]{24,})\b'''
keywords = ["hvb.", "hvs."]
confidence = "high"
```

**Example B: Generic API Key with Entropy Verification**
```toml
[[rules]]
id = "corp-api-key"
description = "Internal corporate service API key"
regex = '''\bcorp_live_[A-Za-z0-9]{32}\b'''
keywords = ["corp_live_"]
entropy = 3.5
confidence = "high"
```

---

### 3. Configuring Allowlists (`[allowlist]`)

Allowlists prevent false positives on known mock values, documentation tokens, or test vectors.

```toml
[allowlist]
description = "Global test and documentation example patterns allowlist"
regexes = [
  '''AKIAIOSFODNN7EXAMPLE''',
  '''wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY''',
  '''sk-dummy-.*'''
]
stopwords = [
  "dummy_token_123456",
  "test_secret_placeholder"
]
```

- `regexes`: Regular expressions that, when matching a candidate finding, immediately dismiss it.
- `stopwords`: Exact string tokens that should never be flagged as leaks.

---

### 4. Configuration Workflow: Validate, Test & Reload

#### Step 1: Validate configuration syntax
Run the built-in Betterleaks validator inside the container:
```bash
docker exec betterleaks betterleaks config check -c /app/config/betterleaks.toml
```
If valid, the command returns exit code `0` with no errors.

#### Step 2: Test your new rule via stdin
Verify that your rule triggers as expected:
```bash
echo "Testing token: hvs.CAESIJL8k2jKlq0Pq1zWmNoPqRstUvwXyZaBcDeFgHiJkLmNoPqRs" | \
  docker exec -i betterleaks betterleaks stdin -c /app/config/betterleaks.toml --report-format json -r - --no-banner
```

#### Step 3: Inspect the fully resolved rule catalog
Inspect all 450+ active rules (including your custom rules):
```bash
docker exec betterleaks betterleaks config show -c /app/config/betterleaks.toml
```

#### Step 4: Apply changes (Zero-Downtime Hot Reload)
Because `betterleaks.toml` is volume-mounted from the host into `/app/config/betterleaks.toml`, simply restart the container:
```bash
docker compose restart betterleaks
```
During startup, Presidio automatically queries `betterleaks config show` and registers your new rule IDs as supported Presidio entity types:
```text
betterleaks | [INFO] Betterleaks loaded 453 rules into supported entities.
betterleaks | [INFO] Presidio Analyzer initialized with Betterleaks Custom Recognizer (400+ rules)
```

---

## 🧪 Verification & Usage Examples

### 1. Unified Redaction (`POST /redact`)

```bash
curl -s -X POST http://localhost:8090/redact \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Hello John Doe (john@example.com), here is my key: ghp_123456789012345678901234567890123456"
  }' | jq .
```

Output:
```json
{
  "has_secrets": true,
  "findings_count": 3,
  "clean_text": "Hello <PERSON> (<EMAIL_ADDRESS>), here is my key: <GITHUB_PAT>",
  "findings": [
    { "entity_type": "GITHUB_PAT", "start": 51, "end": 91, "score": 1.0 },
    { "entity_type": "EMAIL_ADDRESS", "start": 16, "end": 32, "score": 1.0 },
    { "entity_type": "PERSON", "start": 6, "end": 14, "score": 0.85 }
  ]
}
```

Both **PII** (`PERSON`, `EMAIL_ADDRESS`) and **Technical Secrets** (`GITHUB_PAT`, `VAULT_TOKEN`) are identified and redacted in a single pass.

---

## 🔌 Stack Integrations

### 1. Open-WebUI (Human Conversations Guardrail)
Add the inlet filter from [`integrations/openwebui_filter.py`](integrations/openwebui_filter.py) into Open-WebUI:
1. Go to Open-WebUI **Admin Panel** > **Functions**.
2. Click **+** (Add Function) and paste the contents of `openwebui_filter.py`.
3. Configure the valve:
   - `betterleaks_url`: `http://betterleaks:8080` (or `http://host.docker.internal:8090` for host testing)
   - `action`: `redact` (replaces secrets with `<ENTITY_TYPE>`) or `block` (rejects the prompt with a security alert)
4. Enable the filter globally or for specific models. Any secret or PII typed by a human is redacted before reaching the LLM.

### 2. LiteLLM (Gateway-Level Presidio Integration)
Because this service exposes the exact standard Microsoft Presidio endpoints (`/analyze` and `/anonymize`), LiteLLM can use it natively via its built-in Presidio guardrail:
```yaml
litellm_settings:
  callbacks: ["presidio"]
```
Environment variables:
```bash
PRESIDIO_ANALYZER_API_BASE="http://betterleaks:8080"
PRESIDIO_ANONYMIZER_API_BASE="http://betterleaks:8080"
```

### 3. MCP Tool Calls & Results Guardrails (optional, via Agentgateway)
Betterleaks implements the `ExtMcp` gRPC wire protocol defined by the open-source [Agentgateway](https://agentgateway.dev) project. If you run Agentgateway in front of your MCP servers, it can intercept Model Context Protocol (MCP) tool calls (`tools/call`) using its Envoy-based `mcpGuardrails` policy:

```yaml
mcp:
  gateways:
    - default
  policies:
    apiKey:
      mode: strict
      keys:
        - key: "<YOUR_MCP_API_KEY>"
    mcpGuardrails:
      processors:
        - kind: remote
          host: "betterleaks:50052"
          failureMode: failOpen
          methods:
            "tools/call": full
```

- **Protocol**: Wire-protocol gRPC service `agentgateway.dev.ext_mcp.ExtMcp` (from `betterleaks/proto/ext_mcp.proto`) listening on port `50052`.
- **`CheckRequest`**: Intercepts MCP tool arguments (`params`) and redacts credentials before dispatching to upstream tools (e.g. SearXNG).
- **`CheckResponse`**: Intercepts tool outputs (`result`) and sanitizes findings before returning results into the agent / LLM conversation context.
- **JSON Safety**: Deserializes JSON payloads, recursively sanitizes strings, and serializes back to standard JSON bytes, guaranteeing zero formatting corruption.

### 4. Ephemeral Vaulted Tokenization (Developer Workflows)
Static redaction (e.g. replacing an API token with `<GITHUB_PAT>`) protects upstream models, but it breaks practical coding workflows: when a user asks the LLM to generate a script with their token, the model outputs `<GITHUB_PAT>` and forces the user to manually paste their secret back in.

With reversible vaulted tokenization:
1. **Inlet Tokenization (`POST /tokenize`)**: When a secret is detected, Betterleaks generates an opaque surrogate token (e.g. `TOK_GITHUB_PAT_3a7b9c1d2e4f`).
2. **Zero-Trust AES-256-GCM Encryption**: The secret is encrypted client-side before touching Redis using `TOKEN_ENCRYPTION_KEY` (generated in HashiCorp Vault KV v2 and rendered into RAM tmpfs). Redis (DB 2) only ever stores authenticated ciphertext (`enc:<base64(nonce + ciphertext + tag)>`) with a short TTL (default: 300 seconds). Even a raw memory dump of Redis reveals zero credentials.
3. **Upstream Inference**: The LLM receives only the surrogate token and generates code reasoning over it, never seeing the raw credential.
4. **Outlet Rehydration (`POST /detokenize`)**: When the LLM completion is returned to the user session, the outlet filter queries Redis, decrypts the ciphertext in memory, and seamlessly rehydrates `TOK_GITHUB_PAT_3a7b9c1d2e4f` back into the real token for copy-paste convenience.
5. **Configuration in Open-WebUI Filter**:
   - Set valve `action="tokenize"`
   - Set valve `tokenize_ttl=300` (configurable in seconds)

---

## 🧪 Automated Tests

Run the test suite inside Docker:
```bash
docker run --rm betterleaks-presidio:test pytest -v
```
Or directly on host with dependencies installed:
```bash
pytest betterleaks/tests/ -v
```
