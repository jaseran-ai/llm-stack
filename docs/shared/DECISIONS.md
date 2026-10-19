# Register of Architectural Decisions

This document records architectural decisions made by the project owner. Every decision has an identifier, a timestamp, context, considered options, the chosen option, and links to the associated Architectural Decision Record (ADR) in `docs/architecture/adr/`.

---

## Decision Log

### Q1 — Single Source of Truth for Identity & Access Management
* **Date**: 2026-08-15
* **Decision**: `Q1-AUTHENTIK`
* **Options Considered**:
  * `Q1-AUTHELIA`: Lightweight, but lacks native OIDC provider and granular dynamic application blueprints.
  * `Q1-KEYCLOAK`: Heavy Java footprint (violates single-machine portability and lightweight constraints).
  * `Q1-AUTHENTIK` **(Chosen)**: Single lightweight IdP supporting Forward-Auth (Pattern A) and Native OIDC (Pattern B) with declarative YAML blueprints.
* **Associated ADR**: [ADR 0001: Authentik Unified Identity and RBAC](../architecture/docs/adr/0001-authentik-unified-identity-and-rbac.md)

---

### Q2 — Secrets Management Architecture
* **Date**: 2026-08-20
* **Decision**: `Q2-VAULT-TMPFS`
* **Options Considered**:
  * `Q2-STATIC-ENV`: Clear-text `.env` file on host disk (risks accidental commit, disk forensic recovery, and multi-tenant disclosure).
  * `Q2-OPENBAO`: Fork of Vault; evaluated for multi-tenant teams, deprioritized until real multi-operator need.
  * `Q2-VAULT-TMPFS` **(Chosen)**: HashiCorp Vault KV v2 dynamic seeding + Vault Agent rendering into an isolated 64MB memory-backed `tmpfs` volume with `0700` / `0600` permissions.
* **Associated ADR**: [ADR 0002: Vault KV v2 and tmpfs Memory Secrets](../architecture/docs/adr/0002-vault-kv-v2-and-tmpfs-memory-secrets.md)

---

### Q3 — Ingress Proxy & Reverse Proxy Engine
* **Date**: 2026-08-22
* **Decision**: `Q3-TRAEFIK-V3`
* **Options Considered**:
  * `Q3-CADDY`: Required custom build with non-standard plugins for Cloudflare DNS-01 ACME; rigid middleware pipeline.
  * `Q3-TRAEFIK-V3` **(Chosen)**: Native Docker label routing, dynamic middleware chaining (Forward-Auth, security headers, rate limiting), and native metrics exporter.
* **Associated ADR**: [ADR 0003: Traefik v3 Ingress and Security Headers](../architecture/docs/adr/0003-traefik-v3-ingress-and-security-headers.md)

---

### Q4 — Internal TLS and Certificate Verification Plane
* **Date**: 2026-10-18
* **Decision**: `Q4-INTERNAL-TLS-LOCAL-CA`
* **Options Considered**:
  * `Q4-GLOBAL-BYPASS`: Setting `NODE_TLS_REJECT_UNAUTHORIZED="0"` and `PYTHONHTTPSVERIFY="0"` (insecure; vulnerable to machine-in-the-middle attacks).
  * `Q4-PUBLIC-LETSENCRYPT`: Exposing internal backend ports for ACME challenges (violates zero-trust isolation).
  * `Q4-INTERNAL-TLS-LOCAL-CA` **(Chosen)**: Encrypted internal listeners (Vault TLS), local root CA injection into Node.js runtimes (`NODE_EXTRA_CA_CERTS`), and strict preservation of public CA trust for outbound requests.
* **Associated ADR**: [ADR 0004: Internal TLS and Local CA Injection](../architecture/docs/adr/0004-internal-tls-and-local-ca-injection.md)

---

### Q5 — PII & Secrets Redaction Pipeline
* **Date**: 2026-09-25
* **Decision**: `Q5-BETTERLEAKS-PRESIDIO-AES`
* **Options Considered**:
  * `Q5-LLM-GUARD-HEAVY`: Heavy GPU/PyTorch dependencies (violates lightweight single-machine constraint).
  * `Q5-IRREVERSIBLE-MASKING`: Irreversible token masking `[REDACTED]` (breaks code debugging workflows and downstream tool execution).
  * `Q5-BETTERLEAKS-PRESIDIO-AES` **(Chosen)**: Lightweight Go + Python Presidio service with bidirectional stream filtering and client-side AES-256-GCM encrypted reversible tokenization stored in Redis.
* **Associated ADR**: [ADR 0005: Betterleaks Presidio Redaction and Redis Tokenization](../architecture/docs/adr/0005-betterleaks-presidio-redaction-and-redis-tokenization.md)

---

### Q6 — S3 Object Storage IAM Partitioning
* **Date**: 2026-10-18
* **Decision**: `Q6-SEAWEEDFS-SCOPED-IAM`
* **Options Considered**:
  * `Q6-SHARED-ADMIN-KEY`: Reusing `seaweed_admin` credentials across all workloads (violates least-privilege principle).
  * `Q6-SEAWEEDFS-SCOPED-IAM` **(Chosen)**: Automated provisioning of a scoped `langfuse_app` IAM identity in Vault KV v2, restricted strictly to `Read:langfuse`, `Write:langfuse`, `List:langfuse`, and `Tagging:langfuse`.
* **Associated ADR**: [ADR 0006: SeaweedFS Least-Privilege S3 IAM](../architecture/docs/adr/0006-seaweedfs-least-privilege-s3-iam.md)

---

### Q7 — Network Segmentation Model
* **Date**: 2026-10-18
* **Decision**: `Q7-MULTI-TIER-SEGMENTATION`
* **Status**: Accepted
* **Options Considered**:
  * `Q7-SINGLE-BRIDGE`: Legacy single bridge `llm-stack_default`.
  * `Q7-MULTI-TIER-SEGMENTATION` **(Chosen)**: Multi-tier segmentation featuring a dedicated air-gapped `internal-backend` (`llm-stack_backend`, `internal: true`) isolating `postgres`, `clickhouse`, and `redis` with zero internet access, dual-homed application consumers, and Traefik Docker provider network pinning.
* **Associated ADR**: [ADR 0007: Multi-Tier Network Segmentation](../architecture/docs/adr/0007-multi-tier-network-segmentation.md)

---

### Q8 — Documentation Publication & Access Control Model
* **Date**: 2026-10-18
* **Decision**: `Q8-DOCS-FORWARD-AUTH`
* **Status**: Accepted
* **Options Considered**:
  * `Q8-PUBLIC-HOSTING`: Public unauthenticated hosting (rejected; exposes sensitive architecture and operational details).
  * `Q8-BASIC-AUTH`: HTTP Basic Auth (rejected; bypasses centralized identity, auditing, and dashboard).
  * `Q8-DOCS-FORWARD-AUTH` **(Chosen)**: Authentik Forward-Auth (Pattern A) via Traefik with declarative YAML blueprints. `docs-user` (`https://docs.${DOMAIN}`) is accessible to `users` and `admins`; `docs-architecture` (`https://arch.${DOMAIN}`) is strictly restricted to `admins`. Both sites feature official Docusaurus tiles on Authentik dashboard and automated Gatus GitOps monitoring.
* **Associated ADR**: [ADR 0008: Documentation Hosting and RBAC via Authentik Forward-Auth](../architecture/docs/adr/0008-documentation-hosting-forward-auth.md)


