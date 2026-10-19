# 8. Crosscutting Concepts

This section describes universal architectural patterns and cross-cutting concepts applied across all services in the LLM Stack.

---

## 8.1 Prompt Versioning & Model Routing

* **Prompt Management & Tracking**: Every prompt executed through LiteLLM or Open WebUI is assigned a trace ID and shipped to Langfuse. Changes in system prompts, temperature parameters, and token counts are versioned, enabling regression evaluation.
* **Model Routing**: LiteLLM exposes every model under a stable alias (`lfm2-1.2b-rag` by default, served locally by Ollama). Additional local or remote models can be declared in `litellm/custom_models.yaml` without changing client code.
* **Fallback Cascades**: LiteLLM defines declarative fallback cascades. If an upstream provider returns `HTTP 429 Rate Limit` or `HTTP 500`, the request automatically fails over to the next configured model without client disruption.

---

## 8.2 In-Flight Privacy & Guardrail Architecture

* **Dual-Engine Redaction**:
  - **Betterleaks (Go)**: High-throughput pattern matching against thousands of known API key signatures (AWS, GitHub, OpenAI, Slack, private keys).
  - **Presidio Analyzer (Python)**: Contextual Named Entity Recognition (NER) models for detecting personal names, email addresses, phone numbers, and physical addresses in English and French.
* **Reversible Vaulted Tokenization**:
  - Sensitive values are replaced with deterministic surrogate tokens.
  - The surrogate-to-cleartext mapping is stored in Redis encrypted with client-side **AES-256-GCM**.
  - Decryption keys are managed dynamically via HashiCorp Vault KV v2.
* **MCP Tool Guardrails (optional)**: Betterleaks exposes an `ExtMcp` gRPC endpoint (`50052`) compatible with the open-source Agentgateway project, allowing MCP tool arguments and results to be redacted when such a gateway is deployed in front of MCP servers.

---

## 8.3 In-Memory Secrets Isolation & Lifecycle

* **Zero-Disk Ingestion**:
  1. `setup.sh` generates cryptographic secrets via `openssl rand -hex 32`.
  2. Secrets are pushed via HTTPS into HashiCorp Vault KV v2 storage (`secret/data/...`).
  3. Vault Agent authenticates via scoped AppRole credentials.
  4. Vault Agent renders Consul-template files (`.tpl`) into a RAM-backed `tmpfs` mount (`/vault/secrets_ram`).
  5. Applications mount `/vault/secrets_ram/*.env:ro` as read-only volumes.
  6. File permissions are strictly enforced (`0700` directory, `0600` files).

---

## 8.4 Internal PKI & Certificate Trust Model

* **Self-Signed Internal Certificate Authority (CA)**:
  - Generated during `setup.sh` with a 10-year validity.
  - Subject Alternative Names (SAN) cover `*.${DOMAIN}`, `${DOMAIN}`, `DNS:vault`, `DNS:localhost`, and `IP:127.0.0.1`.
* **Trust Store Injection**:
  - The local CA certificate (`traefik/certs/tls.crt`) is mounted into `/etc/ssl/certs/local-ca.crt:ro`.
  - Node.js applications configure `NODE_EXTRA_CA_CERTS: "/etc/ssl/certs/local-ca.crt"`, appending the internal CA to Mozilla roots without overriding them.
  - Insecure bypass flags (`NODE_TLS_REJECT_UNAUTHORIZED: "0"`, `PYTHONHTTPSVERIFY: "0"`) are strictly eliminated.

---

## 8.5 Startup Dependency Graph & Lifecycle

To eliminate race conditions and deadlocks during initialization:
1. **Tier 1 (Datastores)**: `postgres`, `redis`, `clickhouse`, `seaweedfs` initialize and verify health.
2. **Tier 2 (Secrets & Identity)**: `vault` unseals, `vault-agent` renders tmpfs secrets, `authentik-server` boots and applies Tier 00 blueprints.
3. **Tier 3 (Ingress & Outposts)**: Authentik applies Tier 10 blueprints; Traefik binds the embedded Forward-Auth outpost.
4. **Tier 4 (Gateways & Applications)**: `litellm`, `betterleaks`, `open-webui`, `langfuse`, and `grafana` launch after dependencies report healthy.
