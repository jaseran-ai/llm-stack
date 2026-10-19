# ADR 0003: Traefik v3 Ingress and Security Headers

* **Status**: Accepted
* **Deciders**: LLM Stack maintainers
* **Date**: 2026-08-22
* **Technical Story**: Ingress standardization and perimeter security hardening

## Context and Problem Statement

The platform previously used Caddy as a reverse proxy, which required custom container builds with non-standard plugins for DNS ACME challenges. It lacked declarative middleware chaining for forward-auth and robust metric instrumentation. Furthermore, HTTP responses lacked production security headers, exposing users to clickjacking and MIME sniffing risks.

## Decision Drivers

* Native Docker provider integration with automatic container route discovery via labels.
* Declarative middleware chaining for Forward-Auth and security policies.
* Built-in Prometheus metrics scraping endpoint.
* Strict HTTP security header enforcement across all entry points.

## Considered Options

1. **Caddy**: Simple configuration, but custom plugins required maintenance overhead and lacked clean forward-auth middleware ergonomics.
2. **Nginx**: Robust, but dynamic upstream discovery in Docker requires reload daemons or commercial extensions.
3. **Traefik v3**: Native Docker container label discovery, first-class middleware chaining, and official Prometheus metrics exporter.

## Decision Outcome

Chosen option: **Traefik v3**, combined with a global `security-headers@file` middleware enforcing HSTS, X-Frame-Options, Content-Type nosniff, and strict referrer policy.

### Positive Consequences

* No custom image build needed; standard upstream image with pinned multi-arch digest.
* Router middleware chaining seamlessly applies Authentik Forward-Auth and security headers in a single pipeline.
* Native `:8082` metrics endpoint provides per-service and per-router latency, request count, and HTTP status metrics to Prometheus.

### Negative Consequences

* Traefik label syntax in `docker-compose.yml` is verbose.
