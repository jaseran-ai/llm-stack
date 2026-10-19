# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] - 2026-10-19 — Initial Public Release

### Added
- **Core LLM platform**: Ollama with a CPU-friendly bundled model, LiteLLM gateway (virtual keys, budgets, Prometheus metrics, Langfuse OpenTelemetry tracing) and Open WebUI with Qdrant RAG and SearXNG private web search.
- **LLMOps**: Langfuse (web + worker) backed by PostgreSQL, ClickHouse, Redis and SeaweedFS S3, with CHouse UI for ClickHouse exploration and a scoped rollback workflow for Langfuse snapshots.
- **Unified identity**: Authentik as the single IdP, configured through three declarative blueprint tiers (core identity & RBAC groups, Forward-Auth proxy providers with the embedded outpost, native OIDC applications).
- **Secrets management**: HashiCorp Vault KV v2 seeded by `setup.sh`, with Vault Agent rendering per-service secrets into a memory-backed tmpfs (`0700`/`0600`).
- **Privacy guardrails**: Betterleaks, a Presidio-compatible secret and PII redaction service used by the LiteLLM guardrail and the Open WebUI filter, with reversible AES-256-GCM tokenization backed by Redis and an optional MCP `ExtMcp` gRPC endpoint.
- **Ingress & DNS**: Traefik v3 with security headers and internal TLS; three DNS modes (`hosts`, embedded CoreDNS, Cloudflare Zero Trust Tunnel provisioned with Terraform).
- **Observability**: Prometheus, Alertmanager, Grafana dashboards and alert rules, Loki + Vector log pipeline, cAdvisor, node-exporter, Gatus health monitoring and Dozzle.
- **Network segmentation**: databases and caches isolated on an internal-only Docker network.
- **Documentation**: arc42 architecture specification with C4 diagrams and ADRs, and a Diátaxis user guide, both in English and French.
- **Quality gates**: shellcheck, yamllint, Gitleaks, Trivy, Markdown link and startup-graph checks, script unit tests, and a containerized UAT environment; all runnable locally through the `Makefile`.
