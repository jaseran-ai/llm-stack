# 4. Solution Strategy

This section summarizes the fundamental architectural strategies and technology decisions that shape the LLM Stack.

---

## 4.1 Fundamental Architecture Strategies

1. **Defense-in-Depth Layering**:
   Security is not delegated to a single perimeter component. Ingress security (Cloudflare Tunnel, Traefik headers) is backed by mandatory identity verification (Authentik Forward-Auth and Native OIDC), internal TLS listeners (Vault), memory-isolated secrets (`tmpfs`), and in-flight PII redaction (Betterleaks).

2. **Declarative Everything (CaC)**:
   Every configuration is declarative:
   * **Infrastructure**: Docker Compose (`docker-compose.yml`) + Cloudflare Terraform (`cloudflare/`).
   * **Identity & Access**: Authentik YAML Blueprints (`authentik/blueprints/`).
   * **Observability**: Prometheus alerting rules (`prometheus/rules/`), Grafana datasources, and Gatus probes (`gatus/config.yaml`).
   * **Model Routing**: LiteLLM configuration (`litellm/litellm-config.yaml`).

3. **Memory-First Secrets Plane**:
   Physical non-volatile storage is treated as untrusted for secrets. All generated credentials, tokens, and encryption keys are injected into HashiCorp Vault KV v2 and rendered by Vault Agent into a volatile RAM-backed `tmpfs` mount (`/vault/secrets_ram`). Secrets cease to exist on disk power loss.

4. **Zero-Trust Tokenization & Privacy**:
   Rather than simple irreversible masking (`[REDACTED]`), the platform implements reversible vaulted tokenization. Sensitive data is substituted with randomized surrogate tokens, while the cleartext-to-surrogate mapping is stored in Redis encrypted with AES-256-GCM.

5. **Self-Contained Local Ingestion & Inference**:
   The stack provides out-of-the-box local inference via Ollama (`lfm2-1.2b-rag`), local S3 storage via SeaweedFS, and local vector indexing via Qdrant, guaranteeing functional independence from external vendors.

---

## 4.2 Technology Stack Decisions

| Technology Area | Selected Technology | Strategic Rationale |
|---|---|---|
| **Reverse Proxy** | **Traefik v3** | Dynamic Docker label routing, middleware chaining, and native Prometheus metrics. |
| **Identity Provider** | **Authentik** | Dual-pattern auth (Forward-Auth + OIDC), declarative blueprints, native dashboard. |
| **Secrets Engine** | **HashiCorp Vault 2.2** | KV v2 engine, AppRole authentication, automated template rendering into tmpfs. |
| **LLM Gateway** | **LiteLLM v1.105** | OpenAI-compatible translation across 100+ providers, fallbacks, and cost tracking. |
| **Guardrails** | **Betterleaks + Presidio** | High-speed secret scanning, dual-language NER PII detection, reversible AES tokenization. |
| **Vector DB** | **Qdrant v1.19** | Fast Rust-based HNSW vector indexing, low memory footprint (512MB limit). |
| **Object Storage** | **SeaweedFS 4.48** | Ultra-fast Apache 2.0 S3 storage with AWS SigV4 and granular IAM policies. |
| **Relational DB** | **PostgreSQL 18.6** | Robust multi-database isolation for Authentik, LiteLLM, Langfuse, and CHouse UI. |
| **Analytics DB** | **ClickHouse 26.7** | Extreme throughput columnar database for high-volume Langfuse tracing spans. |
| **Observability** | **Prometheus + Loki + Grafana** | Unified metrics, log streams, and interactive GitOps dashboards. |
