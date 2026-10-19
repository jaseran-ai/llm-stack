# Open WebUI Architecture & Operational Reference

Open WebUI serves as the primary conversational interface for users and administrators interacting with models hosted on Ollama and routed through LiteLLM.

---

## 🏛️ Architecture & Integration

- **Container Port**: Exposed on `127.0.0.1:${OPEN_WEBUI_PORT}:8080` (defaults to `:8080`).
- **Reverse Proxy & SSO**: Protected behind Traefik and Authentik Forward-Auth at `https://chat.${DOMAIN}`.
- **Upstream LLM Provider**: Connects via Docker internal networking to LiteLLM at `http://litellm:4000/v1`.
- **Vector Database**: Connects to Qdrant at `http://qdrant:6333` for RAG and document embeddings.
- **Web Search Engine**: Connects to the self-hosted SearXNG instance at `http://searxng:8080`.

---

## 🔑 Authentication & Forward-Auth Mapping

Open WebUI uses Authentik Forward-Auth via the `WEBUI_AUTH_TRUSTED_EMAIL_HEADER="X-Authentik-Email"` environment variable:
- Traefik forwards the authenticated user's email header to Open WebUI.
- Post-startup provisioning scripts (`open-webui/provision.sh` / `open-webui/scripts/provision.py`) can interact directly with the internal API by injecting `X-Authentik-Email: admin@${DOMAIN}` without needing local database credentials.

---

## 🛠️ Post-Startup Provisioning (`open-webui/provision.sh`)

Open WebUI seeds its internal SQLite database once on first initialization. Certain settings cannot be modified by environment variables alone after initial boot:

### 1. RBAC & Default Role Enforcement
- By default, unconfigured deployments auto-escalate new users to `admin`.
- `provision.py` explicitly forces `DEFAULT_USER_ROLE=user` via the API and reconciles existing accounts, ensuring users from Authentik's `users` group remain non-admin users.

### 2. Model Access Grants (Least-Privilege)
- In Open WebUI, model visibility defaults to deny for standard `user` accounts unless an explicit public wildcard grant exists.
- The provisioner automatically registers public read grants (`{"principal_type": "user", "principal_id": "*", "permission": "read"}`) on all LiteLLM base models (`lfm2.5-thinking-1.2b`, `lfm2.5-thinking-1.2b-no-think`, `lfm2.5-thinking-1.2b-protected`).

### 3. Web Search Configuration
- Configures `ENABLE_WEB_SEARCH=True` and `WEB_SEARCH_ENGINE=searxng` targeting `http://searxng:8080/search?q=<query>`.

### 4. Knowledge Base & Custom RAG Assistant
- Idempotently uploads the reference 10-Q sample PDF (`open-webui/aapl-20260627.pdf`) to create the knowledge collection in Qdrant.
- Creates or updates the virtual model `knowledge-search-assistant` with the reference knowledge base pre-attached.
