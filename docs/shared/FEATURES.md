# Feature Catalog & Status Matrix

This catalog tracks every functional feature of the LLM Stack. Each feature has a stable identifier, an operational status verified by empirical test suites, and references to its implementing components and tests.

---

## Catalog Status Legend
- **Active**: Fully implemented, configured as code, and validated by live test suites (`./smoke_test.sh`).
- **Proposed**: Designed and specified, pending implementation and user sign-off.
- **Deprioritized**: Formally evaluated and parked in the backlog until explicit production demand.

---

## 1. Identity, Access & Ingress

| Feature ID | Name | Status | Delivering Components | Verification Proof |
|---|---|---|---|---|
| `FEAT-AUTH-01` | Unified Single Sign-On (SSO) | **Active** | Authentik Server & Worker | `smoke_test.py:test_authentik_oidc` |
| `FEAT-AUTH-02` | Forward-Auth Traefik Middleware (Pattern A) | **Active** | Traefik v3, Authentik Embedded Outpost | `smoke_test.py:test_forward_auth` |
| `FEAT-AUTH-03` | Native OIDC Authentication (Pattern B) | **Active** | Authentik OIDC Providers, LiteLLM, Langfuse | `smoke_test.py:test_langfuse_oidc` |
| `FEAT-AUTH-04` | Role-Based Access Control (RBAC) | **Active** | Authentik Groups (`admins`, `users`) | `smoke_test.py:test_rbac_restrictions` |
| `FEAT-INGR-01` | Cloudflare Zero Trust Ingress Tunnel | **Active** | Cloudflared, Terraform IaC | `terraform-validate`, DNS status |
| `FEAT-INGR-02` | Strict Production Security Headers | **Active** | Traefik Dynamic Configuration | `smoke_test.py:test_security_headers` |
| `FEAT-INGR-03` | DNS Anti-Spoofing (DMARC & CAA) | **Active** | Cloudflare Terraform (`main.tf`) | `make terraform-validate` |

---

## 2. Secrets Management & Core Security

| Feature ID | Name | Status | Delivering Components | Verification Proof |
|---|---|---|---|---|
| `FEAT-SECR-01` | Dynamic Secret Seeding in Vault KV v2 | **Active** | Vault 2.2.0, `vault/scripts/provision.py` | `smoke_test.py:test_vault_secret_read` |
| `FEAT-SECR-02` | In-Memory tmpfs Secrets Isolation | **Active** | Vault Agent, Docker tmpfs mount | `test_migrate_secrets.py` |
| `FEAT-SECR-03` | AppRole Authentication Policy | **Active** | Vault Policy & AppRole Engine | `smoke_test.py:test_vault_approle` |
| `FEAT-SECR-04` | Internal TLS Listener & Mutual Trust | **Active** | Vault Server, Traefik `serversTransport` | `smoke_test.py:test_vault_tls` |
| `FEAT-SECR-05` | Local Root CA Injection without Global Bypass | **Active** | Traefik SAN Certificate, `NODE_EXTRA_CA_CERTS` | `smoke_test.py:test_langfuse_oidc` |

---

## 3. LLM Inference & Routing

| Feature ID | Name | Status | Delivering Components | Verification Proof |
|---|---|---|---|---|
| `FEAT-LLM-01` | Out-of-the-Box Bundled CPU Inference | **Active** | Ollama (`lfm2.5-thinking:1.2b`) | `smoke_test.py:test_ollama_completion` |
| `FEAT-LLM-02` | Multi-Provider Unified Proxy Gateway | **Active** | LiteLLM Proxy v1.105 | `smoke_test.py:test_litellm_routing` |
| `FEAT-LLM-05` | Local Voice Services (Whisper / Piper) | **Planned** | Backlog candidate | Listed in `ROADMAP.md` |

---

## 4. Guardrails & Privacy

| Feature ID | Name | Status | Delivering Components | Verification Proof |
|---|---|---|---|---|
| `FEAT-PRIV-01` | Bidirectional Open WebUI Chat Redaction | **Active** | Betterleaks, Open WebUI Filter | `smoke_test.py:test_betterleaks_filter` |
| `FEAT-PRIV-02` | LiteLLM Presidio Callback Guardrail | **Active** | LiteLLM Guardrail, Presidio Analyzer | `smoke_test.py:test_betterleaks_guardrail` |
| `FEAT-PRIV-03` | Reversible Vaulted Tokenization | **Active** | Betterleaks Tokenizer, Redis AES-256-GCM | `smoke_test.py:test_reversible_tokenization` |

---

## 5. Storage & Persistence

| Feature ID | Name | Status | Delivering Components | Verification Proof |
|---|---|---|---|---|
| `FEAT-STOR-01` | Isolated PostgreSQL 18 Schemas | **Active** | PostgreSQL 18.6, `init-dbs.sql` | `smoke_test.py:test_postgres_query` |
| `FEAT-STOR-02` | ClickHouse Columnar Analytics Store | **Active** | ClickHouse Server 26.7 | `smoke_test.py:test_clickhouse_query` |
| `FEAT-STOR-03` | S3 Object Storage with SigV4 | **Active** | SeaweedFS 4.48 | `smoke_test.py:test_s3_sigv4` |
| `FEAT-STOR-04` | Scoped Least-Privilege S3 IAM Identity | **Active** | SeaweedFS S3 IAM (`langfuse_app`) | `smoke_test.py:test_s3_scoped_iam` |
| `FEAT-STOR-05` | Vector Store for Knowledge Retrieval (RAG) | **Active** | Qdrant v1.19.2 | `smoke_test.py:test_qdrant_rag` |
| `FEAT-STOR-06` | Multi-Tier Network Segmentation | **Proposed** | Docker Compose networks | Architecture ADR 0007 |

---

## 6. Observability & Operations

| Feature ID | Name | Status | Delivering Components | Verification Proof |
|---|---|---|---|---|
| `FEAT-OBS-01` | LLMOps Tracing & Cost Observability | **Active** | Langfuse 4.63, ClickHouse, Postgres | `smoke_test.py:test_langfuse_project` |
| `FEAT-OBS-02` | Metrics Scraping & Centralized Dashboards | **Active** | Prometheus v3.15, Grafana 13.2 | `smoke_test.py:test_grafana_datasources` |
| `FEAT-OBS-03` | Real-Time Container Log Aggregation | **Active** | Vector, Grafana Loki 3.7 | `smoke_test.py:test_loki_ingestion` |
| `FEAT-OBS-04` | Declarative Health Monitoring & Alerting | **Active** | Gatus v5.37, Alertmanager v0.34 | `smoke_test.py:test_gatus_endpoints` |
| `FEAT-OPS-01` | Cryptographic Scoped Backup & Restore | **Active** | `backup.sh`, `restore.sh`, GnuPG AES-256 | `test_backup.py`, `test_restore.py` |
