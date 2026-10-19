# Gatus — Automated Health & Uptime Dashboard

Gatus is a developer-oriented, GitOps-native health dashboard that continuously monitors the operational status of all services in LLM Stack.

---

## 🎯 Role & Responsibilities

- **Automated Health Monitoring**: Periodically probes HTTP, TCP, and DNS endpoints across the internal network.
- **GitOps Declarative Configuration**: Endpoints are defined entirely as code via `gatus/config.yaml.template` and dynamically rendered during `setup.sh`.
- **Extension Points**: Private endpoints can be placed in `gatus/endpoints.d/*.yaml` without polluting version control.

---

## 🐳 Docker Configuration (`docker-compose.yml`)

- **Image**: `twinproduction/gatus:v5.16.0@sha256:...` (multi-arch pinned).
- **Networks**: `default` (connected to Traefik and all monitored services).
- **Volumes**:
  - `./gatus/config.yaml:/config/config.yaml:ro`: Rendered configuration file.
  - `./gatus/endpoints.d:/config/endpoints.d:ro`: Optional extension directory for custom endpoints.
- **Labels (Traefik & Authentik)**:
  - Routed at `https://status.${DOMAIN}`.
  - Forward-Auth enabled with Authentik (`authentik-forward-auth@docker`), restricted to `admins`.
- **Resource Limits**:
  - Memory: `128M`
- **Healthcheck**:
  - `wget --spider http://localhost:8080/health`

---

## 🛠️ Operations & Debugging

```bash
# Verify Gatus health status
docker compose exec gatus wget -qO- http://localhost:8080/health

# Inspect live monitoring logs
docker compose logs gatus --tail 50
```
