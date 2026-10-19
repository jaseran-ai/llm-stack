# Technical Glossary — Single Source of Truth

This glossary establishes canonical definitions for all components, architectural patterns, and security concepts used throughout the LLM Stack.

---

## A
* **ADR (Architectural Decision Record)**: A structured document capturing an important architectural decision made along with its context and consequences (formatted using MADR).
* **Alertmanager**: Prometheus component that handles alerts sent by Prometheus server, managing silencing, inhibition, aggregation, and routing.
* **Authentik**: The unified Identity Provider (IdP) for the platform, providing authentication, single sign-on (SSO), and role-based access control (RBAC).

## B
* **Betterleaks**: A high-performance leak detection and redaction engine integrated with Presidio to detect secrets, API keys, and sensitive PII in real time.
* **Blueprint (Authentik)**: Declarative YAML configuration file defining Authentik tenants, providers, applications, groups, and policies.

## C
* **C4 Model**: A hierarchical architecture modeling method comprising Context, Containers, Components, and Code views.
* **ClickHouse**: An open-source columnar database management system used for high-throughput analytical query workloads, notably Langfuse traces.
* **Cloudflared**: The lightweight daemon connecting the local infrastructure to the Cloudflare Zero Trust network without inbound firewall openings.

## D
* **Diátaxis**: A documentation framework separating content into four distinct modes: Tutorials, How-To Guides, Technical Reference, and Explanations.
* **Dozzle**: A real-time, lightweight web-based log viewer for Docker containers, secured behind Forward-Auth.

## E
* **ExtProc (External Processing)**: An Envoy filter protocol used by MCP-aware gateways (e.g. the open-source Agentgateway project) to offload request/response payload inspection to external gRPC microservices like Betterleaks.

## F
* **Forward-Auth (Pattern A)**: An authentication pattern where an ingress reverse proxy (Traefik) delegates access verification to an external authentication server (Authentik) before forwarding HTTP requests upstream.

## G
* **Gatus**: An automated developer-oriented health dashboard that monitors endpoints and sends alerts using declarative YAML configurations.

## H
* **HSTS (HTTP Strict Transport Security)**: A web security header informing browsers that the site must only be accessed using HTTPS.

## L
* **Langfuse**: An open-source LLMOps observability platform for tracing LLM execution, monitoring latency and token costs, and evaluating prompt versions.
* **LiteLLM**: A lightweight LLM proxy and gateway providing unified OpenAI-compatible interfaces across 100+ LLMs, load balancing, cost tracking, and fallbacks.
* **Loki**: A horizontally scalable, multi-tenant log aggregation system inspired by Prometheus, storing container logs shipped via Vector.

## M
* **MADR (Markdown Any Decision Record)**: A lean, clean Markdown template for recording architectural decisions.
* **MCP (Model Context Protocol)**: An open protocol enabling standardized communication between AI models and development tools or data sources.

## O
* **Ollama**: A lightweight local inference engine running quantized GGUF models directly on the host CPU or GPU without external dependencies.
* **Open WebUI**: A self-hosted, feature-rich web interface for conversational interactions with LLMs, supporting RAG, web search, and custom pipelines.
* **OpenID Connect (OIDC, Pattern B)**: An identity layer built on OAuth 2.0 enabling clients to verify the identity of the end user based on the authentication performed by an authorization server.

## P
* **Presidio**: Microsoft's open-source SDK for detecting and anonymizing Personally Identifiable Information (PII) such as names, phone numbers, and credentials.
* **Prometheus**: A cloud-native systems monitoring and alerting toolkit collecting multi-dimensional time-series metrics.

## Q
* **Qdrant**: A high-performance vector database with an extended filtering engine, utilized for Knowledge Base retrieval in Open WebUI RAG.

## R
* **RAG (Retrieval-Augmented Generation)**: An AI architecture that augments LLM generation with contextual chunks fetched from a vector or document store.

## S
* **SeaweedFS**: A fast, distributed, and S3-compatible object storage system handling media assets, exports, and model artifacts with AWS SigV4 authentication.
* **SearXNG**: A privacy-respecting, metasearch engine providing grounded web search results to Open WebUI and AI agents.
* **SigV4**: AWS Signature Version 4 protocol used for authenticating requests to S3-compatible object storage.
* **Structurizr DSL**: A text-based domain-specific language for defining software architecture models based on the C4 model.

## T
* **tmpfs**: A temporary, volatile file storage facility where files reside entirely in RAM, preventing secrets from touching physical disk blocks.
* **Traefik**: A modern HTTP reverse proxy and ingress controller designed to dynamically route traffic to microservices.

## V
* **Vault (HashiCorp Vault)**: A cryptographic secret management system providing dynamic key generation, KV v2 encrypted storage, and scoped AppRole authentication.
* **Vector**: A high-performance observability data pipeline used to collect Docker logs from the Docker daemon socket and forward them to Loki.
