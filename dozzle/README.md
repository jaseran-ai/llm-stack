# Dozzle — Real-Time Container Log Viewer

Dozzle is a lightweight web application that provides real-time streaming and searching of Docker container logs in a clean web UI.

---

## 🎯 Role & Responsibilities

- **Live Streaming Logs**: Instantly streams stdout and stderr logs for all running containers without needing SSH access or CLI tools.
- **Search & Filter**: Allows developers and administrators to quickly filter logs across services, search regex patterns, and download log dumps.
- **Minimal Footprint**: Read-only access with negligible memory usage (~25MB).

---

## 🐳 Docker Configuration (`docker-compose.yml`)

- **Image**: `amir20/dozzle:v10.6.15@sha256:...` (multi-arch pinned).
- **Networks**: `default` (connected to Traefik).
- **Volumes**:
  - `/var/run/docker.sock:/var/run/docker.sock:ro`: Read-only Docker socket inspection.
- **Labels (Traefik & Authentik)**:
  - Routed at `https://logs.${DOMAIN}`.
  - Forward-Auth enabled with Authentik (`authentik-forward-auth@docker`), restricted strictly to the `admins` group.
- **Resource Limits**:
  - Memory: `128M`
- **Healthcheck**:
  - `wget --spider http://localhost:8080/healthcheck`

---

## 🛠️ Operations & Debugging

```bash
# Verify Dozzle health endpoint
docker compose exec dozzle wget -qO- http://localhost:8080/healthcheck

# Inspect container logs
docker compose logs dozzle --tail 50
```
