# Redis — In-Memory Cache & Message Broker

Redis provides in-memory caching, rate limiting, and asynchronous message broker queues across LLM Stack services.

---

## 🎯 Role & Responsibilities

Redis is utilized by multiple services:
- **`authentik`**: Session store, caching layer, and Dramatiq asynchronous background task queue.
- **`langfuse`**: Real-time event queue, LLM trace buffering, and caching between `langfuse-web` and `langfuse-worker`.
- **`litellm`**: Dynamic rate limiting, RPM/TPM token buckets, and distributed response caching across model endpoints.

---

## 🐳 Docker Configuration (`docker-compose.yml`)

- **Image**: `redis:8.10.0-alpine@sha256:...` (multi-arch pinned).
- **Networks**: `internal-backend` with `internal: true` (strictly isolated from external traffic).
- **Exposed Ports**: Bound to loopback interface `127.0.0.1:6379:6379` only.
- **Volumes**:
  - `redis_data:/data`: Persistent append-only file (AOF) & snapshot storage.
- **Entrypoint Hardening**:
  - `printf 'requirepass %s\nsave 60 1\nloglevel warning\n' "$$REDIS_AUTH" | exec redis-server -`
  - Passes password securely via stdin rather than exposing it in the process table (`ps aux`).
- **Resource Limits**:
  - Memory: `512M`
- **Healthcheck**:
  - `REDISCLI_AUTH="$$REDIS_AUTH" redis-cli ping | grep PONG` (authenticated via environment variable without CLI leak).

---

## 🔐 Credentials & Security

- **Authentication**: Mandatory password protection via `requirepass`.
- **Secrets Management**: Password is generated dynamically during setup (`REDIS_AUTH`) and securely stored in HashiCorp Vault (`secret/data/llm-stack/redis`).
- **RAM tmpfs Injection**: Injected into consuming containers via RAM-backed tmpfs (`vault/secrets_ram/redis.env`).

---

## 🛠️ Operations & Debugging

```bash
# Test Redis authenticated connectivity
docker compose exec redis sh -c 'REDISCLI_AUTH="$$REDIS_AUTH" redis-cli ping'

# Check Redis memory statistics and keys count
docker compose exec redis sh -c 'REDISCLI_AUTH="$$REDIS_AUTH" redis-cli info memory'

# Inspect live container logs
docker compose logs redis --tail 50
```
