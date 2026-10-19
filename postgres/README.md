# PostgreSQL — Relational Database Service

PostgreSQL serves as the primary relational database backend for core identity, metadata, and state management in LLM Stack.

---

## 🎯 Role & Responsibilities

In LLM Stack, PostgreSQL hosts dedicated databases for multiple isolated services:
- **`authentik`**: User accounts, RBAC group memberships, OAuth2/OIDC applications, and policy bindings.
- **`langfuse`**: Relational metadata, user accounts, API keys, organizations, projects, and prompts.
- **`litellm`**: Model spend tracking, user budgets, and API key management tables (`LiteLLM_UserTable`).
- **`chouse_ui`**: RBAC permissions and session management for CHouse UI.

---

## 🐳 Docker Configuration (`docker-compose.yml`)

- **Image**: `postgres:18.4-alpine@sha256:...` (multi-arch pinned).
- **Networks**: `internal-backend` with `internal: true` (strictly isolated, no public exposure).
- **Exposed Ports**: Bound to loopback interface `127.0.0.1:5432:5432` only.
- **Volumes**:
  - `postgres_data:/var/lib/postgresql`: Persistent relational data storage.
  - `./postgres/init:/docker-entrypoint-initdb.d:ro`: Automated database creation scripts on initial bootstrap.
- **Resource Limits**:
  - Memory: `1024M`
- **Healthcheck**:
  - `pg_isready -U postgres -d postgres` (evaluated every 5s with 10 retries).

---

## 🔐 Credentials & Security

- **Authentication**: Secured with `POSTGRES_PASSWORD`, dynamically generated at deployment by `setup.sh` (`openssl rand -hex 32`) and stored in HashiCorp Vault (`secret/data/llm-stack/postgres`).
- **Network Segmentation**: Placed exclusively on the `internal-backend` network, ensuring that application containers can reach PostgreSQL internally while blocking unauthorized external traffic.

---

## 🛠️ Operations & Debugging

```bash
# Connect to PostgreSQL via psql in container
docker compose exec postgres psql -U postgres -d postgres

# Check database connection and list databases
docker compose exec postgres psql -U postgres -c "\l"

# Inspect live container logs
docker compose logs postgres --tail 50
```
