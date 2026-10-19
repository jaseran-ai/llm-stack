# Reference: Configuration & Environment Variables

This document details the configuration variables and secrets used by the LLM Stack.

---

## 1. Global Platform Variables

| Variable | Description | Example / Default | Mandatory? |
|---|---|---|---|
| `DOMAIN` | Base domain name for subdomains and routing | `example.local` | Yes |
| `TZ` | System timezone for logs and cron tasks | `UTC` | Yes |
| `BACKUP_PASSPHRASE` | Cryptographic passphrase for GnuPG AES-256 backup archives | *(Generated randomly)* | Yes |
| `TELEMETRY_ENABLED` | Explicit toggle deactivating third-party telemetry beacons | `false` | Yes |

---

## 2. Secrets Management (Vault KV v2)

All credentials are generated dynamically into Vault KV v2 and rendered into `/vault/secrets_ram/*.env`.

| Environment File | Variable | Description |
|---|---|---|
| `authentik.env` | `AUTHENTIK_SECRET_KEY` | Secret key used for signing Authentik session cookies |
| `authentik.env` | `AUTHENTIK_POSTGRESQL__PASSWORD` | Database password for Authentik PostgreSQL user |
| `litellm.env` | `LITELLM_MASTER_KEY` | Administrative master API key for LiteLLM gateway |
| `litellm.env` | `LITELLM_SALT_KEY` | Key derivation salt for encrypted LiteLLM tokens |
| `langfuse.env` | `LANGFUSE_S3_ACCESS_KEY` | Scoped S3 IAM access key restricted to `langfuse` bucket |
| `langfuse.env` | `LANGFUSE_S3_SECRET_KEY` | Scoped S3 IAM secret key |
| `qdrant.env` | `QDRANT__SERVICE__API_KEY` | API key required to access Qdrant vector database |
| `betterleaks.env` | `BETTERLEAKS_ENCRYPTION_KEY` | 256-bit AES key for client-side encrypted Redis tokenization |

---

## 3. Extension Points

To customize the stack without polluting git:
* **Custom Scrape Targets**: Place Prometheus scrape targets in `prometheus/targets.d/*.yml` (gitignored).
* **Custom Health Endpoints**: Place external monitoring probes in `gatus/endpoints.d/*.yaml` (gitignored).
* **Private LLM Models**: Configure private model endpoints in `litellm/custom_models.yaml`.
* **Local Docker Overrides**: Place developer container overrides in `docker-compose.override.yml` (gitignored).
