# SearXNG — Privacy-Preserving Metasearch Engine

SearXNG is a privacy-respecting, open-source metasearch engine integrated into LLM Stack to provide real-time web search capabilities to conversational agents.

---

## 🎯 Role & Responsibilities

- **Private Metasearch**: Aggregates query results across multiple search engines without user profiling, cookies, or tracking.
- **Agent Web Search (RAG)**: Connects directly to **Open-WebUI** via its JSON API (`format=json`), allowing chat models to browse the live internet for factual information and up-to-date context.

---

## 🐳 Docker Configuration (`docker-compose.yml`)

- **Image**: `searxng/searxng:2026.3.2-30043aa37@sha256:...` (multi-arch pinned).
- **Networks**: `default` (connected to Traefik and Open-WebUI).
- **Volumes**:
  - `./searxng:/etc/searxng:ro`: Read-only mount of `settings.yml` declarative configuration.
- **Labels (Traefik & Authentik)**:
  - Routed at `https://searxng.${DOMAIN}`.
  - Forward-Auth enabled with Authentik (`authentik-forward-auth@docker`), restricting browser access to authenticated users.
- **Resource Limits**:
  - Memory: `512M`
- **Healthcheck**:
  - Evaluates internal HTTP port `http://127.0.0.1:8080/healthz`.

---

## ⚙️ Configuration (`searxng/settings.yml`)

- **JSON API**: Enabled via `search.formats: [html, json]` to allow Open-WebUI to query the engine programmatically.
- **Engines**: Configured with Google, Bing, DuckDuckGo, Wikipedia, and Brave search backends.
- **Secret Key**: Seeded dynamically with `SEARXNG_SECRET_KEY` from Vault.

---

## 🛠️ Operations & Debugging

```bash
# Query the live SearXNG JSON API from inside the network
docker compose exec open-webui curl -s "http://searxng:8080/search?q=test&format=json" | jq .results[0]

# Inspect live SearXNG logs
docker compose logs searxng --tail 50
```
