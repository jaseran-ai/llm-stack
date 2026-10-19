# 5. Building Block View

The Building Block View provides a hierarchical decomposition of the LLM Stack into logical planes and container components.

---

## 5.1 Level 1: Container Decomposition (C4 Container Diagram)

The following diagram details the decomposition of the LLM Stack into individual containerized services and their data connections:

![Container Diagram](@site/docs/c4/svg/structurizr-Containers.svg)

---

## 5.2 Level 2: Architectural Planes

The components are organized into six functional planes:

### 1. Ingress & Perimeter Plane
* **`cloudflared`**: Connects the private container network to Cloudflare's global edge network using outbound tunnels.
* **`traefik`**: Traefik v3 HTTP reverse proxy. Handles routing via Docker container labels, enforces security headers (`HSTS`, `nosniff`, `DENY`), and routes requests through Authentik Forward-Auth middleware.

### 2. Identity & Secret Governance Plane
* **`authentik-server` & `authentik-worker`**: Unified Identity Provider handling authentication flows, session cookies, OAuth2/OIDC token issuance, and embedded Forward-Auth outpost.
* **`vault`**: HashiCorp Vault server operating an internal TLS listener on port `8200`, managing KV v2 secret paths.
* **`vault-agent`**: Daemon authenticating via AppRole to read secrets from Vault and render environment templates into volatile RAM (`/vault/secrets_ram`).

### 3. Serving & Guardrail Plane
* **`litellm`**: OpenAI-compatible LLM router, managing provider fallbacks, latency tracking, budget quotas, and Presidio guardrail callbacks.
* **`betterleaks-presidio`**: Unified Go and Python redaction engine performing regex pattern scanning, spaCy NER analysis, and AES-256-GCM tokenization.

### 4. Interactive Applications Plane
* **`open-webui`**: Conversational web frontend supporting chat completions, multi-modal uploads, RAG document indexing, and web search integration.
* **`searxng`**: Self-hosted privacy metasearch engine delivering search results to Open WebUI.
* **`chouse-ui`**: Lightweight web interface for exploring ClickHouse database tables and running SQL analytical queries.

### 5. Storage & Persistence Tier
* **`postgres`**: PostgreSQL 18 relational database with multi-database initialization (`authentik`, `langfuse`, `chouse_ui`, plus the default `postgres` database used by LiteLLM).
* **`clickhouse`**: Columnar database storing high-frequency Langfuse spans.
* **`seaweedfs`**: Combined master, volume, and S3 server handling file uploads and exports via AWS SigV4 authentication.
* **`qdrant`**: Vector database handling embeddings storage and similarity search for RAG.
* **`redis`**: In-memory cache for Langfuse tasks and encrypted surrogate token store.
* **`ollama`**: Local CPU inference engine hosting the default model (`lfm2.5-thinking:1.2b`).

### 6. Observability & Monitoring Plane
* **`langfuse-web` & `langfuse-worker`**: Open-source LLMOps observability platform tracing prompts, latencies, token consumption, and evaluations.
* **`prometheus`**: Time-series metrics scraper collecting data from Traefik, LiteLLM, Qdrant, cAdvisor, and Node Exporter.
* **`grafana`**: Interactive dashboard visualizer pre-provisioned with stack health, Traefik traffic, and LLM telemetry boards.
* **`vector` & `loki`**: Log aggregation pipeline collecting container stdout/stderr from Docker socket and shipping to Loki TSDB storage.
* **`gatus`**: Automated status page probing HTTP endpoints and alerting on service interruptions.
