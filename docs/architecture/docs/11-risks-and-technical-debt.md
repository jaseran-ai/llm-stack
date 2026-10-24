# 11. Risks and Technical Debt

This section lists the security controls that mitigate known risks, and the limitations that remain open by design.

---

## 11.1 Mitigated Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Secrets rendered in plaintext on persistent host disk. | **High** | Vault Agent renders secrets into a memory-backed `tmpfs` volume (`vault/secrets_ram/`) with `0700`/`0600` permissions. See [ADR 0002](adr/0002-vault-kv-v2-and-tmpfs-memory-secrets.md). |
| Vault listener exposed over unencrypted HTTP. | **High** | TLS listener enabled (`tls_disable = 0`) with SAN certificates; Traefik verifies the backend against the local root CA. |
| Global TLS bypass flags (`NODE_TLS_REJECT_UNAUTHORIZED="0"`, `PYTHONHTTPSVERIFY="0"`). | **High** | Bypass flags removed; the local CA is injected into Node.js runtimes through `NODE_EXTRA_CA_CERTS`. See [ADR 0004](adr/0004-internal-tls-and-local-ca-injection.md). |
| Langfuse using administrative S3 credentials. | **Medium** | Dedicated least-privilege `langfuse_app` identity restricted to the `langfuse` bucket. See [ADR 0006](adr/0006-seaweedfs-least-privilege-s3-iam.md). |
| Private network endpoints committed to version control. | **Low** | Site-specific targets live in gitignored extension points (`gatus/endpoints.d/`, `prometheus/targets.d/`, `litellm/custom_models.yaml`). |
| Missing email anti-spoofing and CA authorization records (Cloudflare mode). | **Medium** | Terraform provisions a strict DMARC (`p=reject`) record and CAA records. |
| Missing HSTS headers and legacy TLS 1.0/1.1 accepted at the edge. | **Medium** | Traefik `security-headers@file` middleware and Cloudflare `min_tls_version = "1.2"`. See [ADR 0003](adr/0003-traefik-v3-ingress-and-security-headers.md). |
| All containers sharing a single flat Docker network. | **Medium** | Databases and caches isolated on the `internal-backend` network (`internal: true`). See [ADR 0007](adr/0007-multi-tier-network-segmentation.md). |
| Public health metadata endpoints, unpinned images, over-privileged default SSO role. | **Medium** | `/api/health` and `/v1/sys/health` shielded by Traefik routers, every image pinned by SHA-256 digest, `AUTH_SSO_DEFAULT_ROLE: "viewer"` for CHouse UI. |
| Redaction bypass through zero-width or confusable Unicode characters. | **Medium** | Betterleaks applies NFKC normalization and strips zero-width separators before analysis. |
| Memory exhaustion through oversized redaction payloads. | **Low** | Betterleaks rejects inputs above 500k characters with HTTP 413. |

---

## 11.2 Open Risks & Accepted Limitations

### 1. Single-Node Deployment
The stack runs on a single Docker host. There is no high availability: a host failure stops every service until it is restored from backups (see `docs/BACKUP_AND_RESTORE.md`).

### 2. Docker Socket Access
Traefik, Vector and Dozzle mount `/var/run/docker.sock` read-only for service discovery and log collection. Read-only access to the Docker API still exposes container metadata and environment variables; these services must stay behind Forward-Auth and must not be exposed directly.

### 3. Internal Certificate Authority
In `TLS_MODE=internal`, clients must trust the locally generated root CA (`traefik/certs/internal-ca.crt`). It is generated per installation by `setup.sh` and is never committed. `TLS_MODE=custom` serves a certificate from the operator's own CA instead; Vault always keeps its certificate from the internal CA.

### 4. Community-Maintained Images
A few components (for example the CHouse UI image) are published by individual maintainers rather than by the upstream project. They are pinned by digest and scanned by Trivy, but receive security updates on the maintainer's schedule.
