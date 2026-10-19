# ADR 0008: Documentation Hosting and RBAC via Authentik Forward-Auth

* **Status**: Accepted
* **Deciders**: LLM Stack maintainers
* **Date**: 2026-10-18
* **Technical Story**: Architecture and User Documentation publication with unified SSO protection

## Context and Problem Statement

The LLM stack maintains two strictly separated Docusaurus documentation sites:
1. `docs-user` (`docs/user/`): User-facing guides, tutorials, how-to, and reference following the Diátaxis framework.
2. `docs-architecture` (`docs/architecture/`): Internal architecture documentation based on arc42, C4 diagrams, and MADR ADRs.

Previously, these documentation sites were compiled and tested in isolation via Docker Compose (`docs/compose.yaml`), but were not published or exposed to users. The project required publishing both documentation sites with zero-trust access control:
- `docs-user` must be accessible to both standard authenticated users (`users` group) and administrators (`admins` group).
- `docs-architecture` contains sensitive architectural blueprints, threat modeling, and internal security topology, and must remain strictly restricted to administrators (`admins` group).
- Both sites must integrate natively into the Authentik application dashboard with official icons, Traefik security headers, and automated Gatus GitOps health monitoring.

## Decision Drivers

* Unified Single Sign-On (SSO) adhering to stack governance (Rule 6).
* Zero unauthenticated access (anonymous visitors strictly blocked with HTTP 302/401).
* Role-Based Access Control (RBAC):
  * User documentation accessible by all authenticated users (`users` + `admins`).
  * Architecture documentation restricted strictly to `admins`.
* Reproducibility as code: all providers, applications, and policy bindings declared in versioned YAML blueprints.
* Containerized, lightweight runtime with Alpine-based Nginx serving pre-compiled static sites.
* Strict dual-language support (English source + French translation).

## Considered Options

1. **Public Unauthenticated Hosting**: Insecure; leaks internal operational topology and architecture.
2. **Basic Authentication (HTTP Basic Auth)**: Out-of-band credentials, lacks centralized auditing, user provisioning, and Authentik dashboard integration.
3. **Pattern A: Authentik Forward-Auth via Traefik (Chosen)**:
   - Traefik intercepts incoming HTTP requests on `docs.${DOMAIN}` and `arch.${DOMAIN}`.
   - Requests are evaluated by the Authentik forward-auth middleware before reaching the documentation web servers.
   - Authentik enforces declarative RBAC policy bindings:
     * `docs-user` allows `admins` and `users` groups.
     * `docs-architecture` allows exclusively `admins` group.
   - Static assets are served by minimal Alpine Nginx containers (`llm-stack-docs-user` and `llm-stack-docs-architecture`) consuming under 128MB RAM each.

## Decision Outcome

Chosen option: **Pattern A: Authentik Forward-Auth via Traefik with Declarative YAML Blueprints**.

### Implementation Details

1. **Docker Compose Service Definitions**:
   - `docs-user`: builds/runs `llm-stack-docs-user`, port `8080`, mapped locally to `127.0.0.1:8085`, memory limit 128MB.
   - `docs-architecture`: builds/runs `llm-stack-docs-architecture`, port `8080`, mapped locally to `127.0.0.1:8086`, memory limit 128MB.
   - Health checks configured with `wget -q -O - http://127.0.0.1:8080/ || exit 1`.
2. **Authentik Declarative Blueprints (`authentik/blueprints/10-forward-auth.yaml`)**:
   - Declared ProxyProviders `docs-forward-auth` and `arch-forward-auth` with `mode: forward_single`.
   - Created Applications `docs` and `arch` with metadata icons (`https://cdn.jsdelivr.net/gh/selfhst/icons/png/docusaurus.png`).
   - Attached Policy Bindings:
     * `docs`: groups `admins` (order 0) and `users` (order 1).
     * `arch`: group `admins` (order 0).
   - Associated both providers with `authentik Embedded Outpost`.
3. **Traefik Reverse-Proxy Routing & Security Headers**:
   - Traefik labels configured on both services attaching `authentik@docker` middleware and standard security headers.
4. **Cloudflare Zero Trust IaC**:
   - Added `"docs"` and `"arch"` subdomains to `cloudflare/variables.tf`.
   - Applied Terraform to generate public CNAME records and tunnel ingress routes.
5. **Gatus GitOps Health Monitoring**:
   - Added automated HTTP health probes for both documentation sites in `gatus/config.yaml.template`.
6. **Empirical Verification (`smoke_test.py`)**:
   - Added `test_docs_user` and `test_docs_arch` validating anonymous blocking, RBAC group enforcement (Alice allowed on user docs, Alice blocked on arch docs, Admin allowed on both), and HTTP 200 on EN and FR endpoints.

### Positive Consequences

* Seamless SSO experience: users log in once through Authentik and access authorized documentation.
* Architecture documentation is cryptographically and logically shielded from non-admin users and anonymous public traffic.
* Both sites appear as tiles in the Authentik central dashboard (`https://home.${DOMAIN}/`).
* 100% reproducible via `./setup.sh` and GitOps blueprints.

### Negative Consequences

* Accessing documentation requires active internet connectivity or local identity provider resolution to complete Authentik OAuth forward-auth flow.
