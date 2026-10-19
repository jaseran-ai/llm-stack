# Loki & Vector — Centralized Log Aggregation Pipeline

Grafana Loki and Timber Vector form the persistent, high-efficiency log ingestion and aggregation pipeline in LLM Stack.

---

## 🎯 Role & Responsibilities

- **Loki**: Horizontally scalable, highly available log storage engine optimized for Kubernetes and Docker environments. It indexes metadata labels rather than full text, keeping disk and memory overhead minimal.
- **Vector**: Lightweight, ultra-fast log collector listening on the Docker daemon socket (`/var/run/docker.sock`). It enriches raw container stdout/stderr streams with container metadata labels (container name, image, service) and ships them into Loki in real time.

---

## 🐳 Docker Configuration (`docker-compose.yml`)

### 1. Loki (`loki`)
- **Image**: `grafana/loki:3.7.6@sha256:...` (multi-arch pinned).
- **Volumes**:
  - `loki_data:/loki`: Persistent log storage and TSDB index.
  - `./loki/loki-config.yml:/etc/loki/local-config.yaml:ro`: Declarative TSDB schema configuration.
- **Retention**: Configured for 30-day automatic log retention.
- **Resource Limits**:
  - Memory: `512M`

### 2. Vector (`vector`)
- **Image**: `timberio/vector:0.57.0-alpine@sha256:...` (multi-arch pinned).
- **Volumes**:
  - `/var/run/docker.sock:/var/run/docker.sock:ro`: Read-only access to container stream events.
  - `./vector/vector.yml:/etc/vector/vector.yml:ro`: Pipeline transform and Loki sink configuration.
- **Resource Limits**:
  - Memory: `256M`

---

## 🛠️ Operations & Debugging

```bash
# Check Loki health readiness
curl -s http://localhost:3100/ready

# Query logs directly from Loki using LogQL via CLI
curl -G -s "http://localhost:3100/loki/api/v1/query" --data-urlencode 'query={service_name="litellm"}' | jq .

# Inspect Vector logs
docker compose logs vector --tail 50
```
