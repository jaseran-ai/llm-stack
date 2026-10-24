workspace "LLM Stack Architecture" "Enterprise Self-Hosted LLM & LLMOps Platform" {

    model {
        user = person "Client / Engineer" "Interacts with chat interfaces, APIs, and administrative dashboards."
        
        llmStack = softwareSystem "LLM Stack" "Unified self-hosted platform for LLM serving, governance, and observability." {
            
            # Ingress & Edge
            traefik = container "Traefik Ingress" "Reverse proxy, TLS termination, and Forward-Auth middleware dispatcher." "Traefik v3" "Ingress"
            cloudflared = container "Cloudflare Tunnel Daemon" "Outbound Zero Trust tunnel terminating edge traffic." "cloudflared" "Ingress"
            
            # Identity & Access
            authentik = container "Authentik IdP" "Single Source of Truth for identity, OIDC provider, and Forward-Auth." "Authentik 2026.8" "Identity"
            vault = container "HashiCorp Vault" "Secrets lifecycle engine, KV v2 encrypted storage, and AppRole token provider." "Vault 2.2.0" "Security"
            
            # User & Gateway Applications
            openwebui = container "Open WebUI" "Chat, Knowledge RAG interface, and model playground." "Python / Svelte" "Application"
            litellm = container "LiteLLM Gateway" "Unified OpenAI-compatible proxy, load balancing, and spend tracking." "LiteLLM v1.105" "Gateway"
            betterleaks = container "Betterleaks + Presidio" "Bidirectional secret detection, PII redaction, and reversible tokenization." "Python / Go" "Security"
            
            # Storage & Persistence Tier (Air-Gapped internal-backend)
            postgres = container "PostgreSQL Database" "Relational storage on air-gapped internal-backend network." "PostgreSQL 18.6" "Database"
            clickhouse = container "ClickHouse Database" "Columnar analytics engine on air-gapped internal-backend network." "ClickHouse 26.7" "Database"
            redis = container "Redis Cache" "In-memory queue and encrypted token store on air-gapped internal-backend." "Redis 8.10" "Database"
            seaweedfs = container "SeaweedFS S3 Storage" "S3 object storage for prompts, exports, and document chunks." "SeaweedFS 4.48" "Database"
            qdrant = container "Qdrant Vector Database" "Vector index and semantic similarity search for RAG." "Qdrant v1.19" "Database"
            
            # Inference Engine
            ollama = container "Ollama Inference Engine" "Bundled local CPU/GPU model runtime (lfm2-1.2b-rag)." "Ollama 0.40" "Inference"
            
            # Observability Tier
            langfuse = container "Langfuse Observability" "LLMOps tracing, prompt evaluation, and telemetry." "Next.js / Node" "Observability"
            prometheus = container "Prometheus Server" "Multi-dimensional metrics scraper and time-series store." "Prometheus v3.15" "Observability"
            grafana = container "Grafana Dashboards" "Unified observability and monitoring visualization." "Grafana 13.2" "Observability"
            loki = container "Grafana Loki" "Centralized log aggregation engine." "Loki 3.7" "Observability"
        }

        # Relationships
        user -> cloudflared "Accesses web interfaces and APIs via HTTPS"
        cloudflared -> traefik "Forwards unencrypted tunnel traffic internally"
        traefik -> authentik "Verifies identity via Forward-Auth middleware"
        traefik -> openwebui "Routes chat UI traffic"
        traefik -> litellm "Routes API completion traffic"
        traefik -> grafana "Routes monitoring dashboard traffic"
        traefik -> langfuse "Routes LLMOps UI traffic"
        
        openwebui -> litellm "Sends inference requests"
        openwebui -> qdrant "Retrieves vector context (RAG)"
        openwebui -> betterleaks "Inspects chat streams for PII leaks"
        
        litellm -> ollama "Dispatches local model execution"
        litellm -> postgres "Stores API keys and spend logs"
        litellm -> langfuse "Ships tracing spans and tokens"
        litellm -> betterleaks "Applies Presidio guardrail callback"
        
        betterleaks -> redis "Persists AES-256-GCM encrypted token mappings"
        
        langfuse -> postgres "Stores projects and users"
        langfuse -> clickhouse "Stores high-throughput telemetry traces"
        langfuse -> seaweedfs "Stores dataset exports (SigV4 scoped IAM)"
        
        prometheus -> litellm "Scrapes /metrics endpoint"
        prometheus -> traefik "Scrapes router metrics (:8082)"
        grafana -> prometheus "Queries metrics time series"
        grafana -> loki "Queries log streams"
    }

    views {
        systemContext llmStack "SystemContext" {
            include *
            autoLayout lr
        }

        container llmStack "Containers" {
            include *
            autoLayout lr
        }

        styles {
            element "Element" {
                color #ffffff
            }
            element "Person" {
                background #08427b
                shape Person
            }
            element "Software System" {
                background #1168bd
            }
            element "Container" {
                background #438dd5
            }
            element "Database" {
                shape Cylinder
                background #2a6496
            }
            element "Gateway" {
                shape Hexagon
                background #207a7a
            }
            element "Security" {
                background #a02040
            }
            element "Observability" {
                background #505050
            }
        }
    }
}
