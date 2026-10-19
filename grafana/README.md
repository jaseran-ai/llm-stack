# Grafana — Visual Observability & Monitoring Dashboards

Grafana is the centralized visualization and analytics dashboard platform for LLM Stack.

---

## 🎯 Role & Responsibilities

- **Unified Visual Dashboards**: Displays real-time operational graphs for system metrics (cAdvisor, node-exporter), reverse proxy traffic (Traefik), vector searches (Qdrant), and LLM token usage (LiteLLM).
- **Log Exploration**: Direct query interface into **Grafana Loki** via LogQL for inspecting container logs and audit events.
- **Declarative Provisioning**: Data sources and dashboards are pre-loaded automatically on boot as code.

---

## 🐳 Docker Configuration (`docker-compose.yml`)

- **Image**: `grafana/grafana-oss:13.1.3@sha256:...` (multi-arch pinned).
- **Networks**: `default` (connected to Traefik, Prometheus, and Loki).
- **Volumes**:
  - `grafana_data:/var/lib/grafana`: Persistent storage for dashboard edits and user preferences.
  - `./grafana/provisioning:/etc/grafana/provisioning:ro`: Declarative datasources (`datasources.yml`) and dashboards (`dashboards.yml`).
- **Labels (Traefik & Authentik)**:
  - Routed at `https://grafana.${DOMAIN}`.
  - Protected by Authentik Forward-Auth SSO. Header mapping automatically passes the authenticated user to Grafana via `GF_AUTH_PROXY_HEADER_NAME: "X-Authentik-Username"`.
- **Resource Limits**:
  - Memory: `512M`
- **Healthcheck**:
  - `wget --spider http://localhost:3000/api/health`

---

## ⚙️ Declarative Provisioning (`grafana/provisioning/`)

- **Data Sources (`datasources/datasources.yml`)**:
  - **Prometheus**: Connected internally to `http://prometheus:9090` (marked as default).
  - **Loki**: Connected internally to `http://loki:3100`.
- **Dashboards (`dashboards/dashboards.yml`)**:
  - Docker Container Monitoring (cAdvisor).
  - Node Exporter host metrics (CPU, RAM, Disk, Network).
  - LiteLLM Spend, Latency, and Token throughput.

---

## 🛠️ Operations & Debugging

```bash
# Check Grafana internal health status
docker compose exec grafana wget -qO- http://localhost:3000/api/health

# Inspect live container logs
docker compose logs grafana --tail 50
```
