# 9. Architecture Decisions

This section indexes all Architectural Decision Records (ADR) governing the LLM Stack. Each decision is documented in the `adr/` directory using the Markdown Any Decision Record (MADR) format.

---

## 9.1 Decision Record Index

| ADR ID | Decision Title | Status | Date | Primary Driver |
|---|---|---|---|---|
| [**ADR 0001**](adr/0001-authentik-unified-identity-and-rbac.md) | Authentik Unified Identity and RBAC | **Accepted** | 2026-08-15 | Consolidation of IdP, OIDC, and dashboard into a single engine. |
| [**ADR 0002**](adr/0002-vault-kv-v2-and-tmpfs-memory-secrets.md) | Vault KV v2 and tmpfs Memory Secrets | **Accepted** | 2026-08-20 | Elimination of plaintext secrets on physical disk storage. |
| [**ADR 0003**](adr/0003-traefik-v3-ingress-and-security-headers.md) | Traefik v3 Ingress and Security Headers | **Accepted** | 2026-08-22 | Native Docker routing, middleware chaining, and HSTS headers. |
| [**ADR 0004**](adr/0004-internal-tls-and-local-ca-injection.md) | Internal TLS and Local CA Injection | **Accepted** | 2026-10-18 | Elimination of global TLS bypass flags and Vault HTTPS hardening. |
| [**ADR 0005**](adr/0005-betterleaks-presidio-redaction-and-redis-tokenization.md) | Betterleaks Presidio Redaction and Redis Tokenization | **Accepted** | 2026-09-25 | Reversible vaulted tokenization with AES-256-GCM encrypted Redis. |
| [**ADR 0006**](adr/0006-seaweedfs-least-privilege-s3-iam.md) | SeaweedFS Least-Privilege S3 IAM | **Accepted** | 2026-10-18 | Isolation of Langfuse S3 bucket access from admin credentials. |
| [**ADR 0007**](adr/0007-multi-tier-network-segmentation.md) | Multi-Tier Network Segmentation | **Proposed** | 2026-10-18 | 4-tier network segmentation isolating database backends. |

---

## 9.2 ADR Governance Rules

* **Immutability of Accepted ADRs**: Once an ADR is marked `Accepted`, its historical context, decision, and drivers are never retroactively modified. If an architectural decision changes, a new superseding ADR is created.
* **Proposals Lifecycle**: ADRs authored by automated assistants remain marked `Proposed` until explicitly ratified by the project owner.
* **MADR Format**: Every ADR strictly includes Status, Deciders, Date, Context, Considered Options, Decision Outcome, and Consequences.
