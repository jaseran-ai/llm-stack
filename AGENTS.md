# AI Agent Rules & Operational Guidelines — `llm-stack`

This document defines the authoritative, binding rules and governance for all AI assistants (Antigravity/Gemini, Claude Code, OpenCode, Cursor, and automated agents) working in this repository.

---

## 🏛️ Core Architecture Governance Rules

1. **Prior Consultation & Approval (Rule 1)**:
   - NEVER make unilateral architectural, networking, database schema, or security changes.
   - Always present a clear diagnostic and plan, and wait for explicit user confirmation before proceeding.

2. **Absolute Reproducibility as Code (Rule 2)**:
   - The entire stack must be 100% reproducible from a clean clone via `./setup.sh`.
   - NO manual GUI clicks, uncommitted DB edits, or opaque manual fixes. Everything belongs in versioned templates, scripts, or `docker-compose.yml`.

3. **Automated Empirical Validation — "Prove It Works" (Rule 3)**:
   - A task is NEVER done based on intent or assumption alone.
   - Every change must be validated with raw proof: HTTP status codes, curl outputs, database queries, live service logs, or `./smoke_test.sh` / `python3 scripts/smoke_test.py`.

4. **Strict Preservation of Data & Volumes (Rule 4)**:
   - NEVER run `docker compose down -v`, `rm -rf` on data directories, or destructive database commands without explicit user instruction.

5. **Zero Hardcoded Secrets & Zero Fallback Defaults (Rule 5)**:
   - NEVER use fallback syntax in `docker-compose.yml` (e.g. `${MY_SECRET:-default}` is FORBIDDEN; use bare `${MY_SECRET}`).
   - Secrets are generated dynamically in `setup.sh` (`openssl rand -hex 32`), stored in Vault KV v2, and rendered into memory-backed tmpfs (`vault/secrets_ram/`).

6. **End-to-End Architectural Integrity & Unified SSO (Rule 6)**:
   - Authentik is the single source of truth for identity and access.
   - New services must use either **Pattern A (Forward-Auth)** or **Pattern B (Native OIDC)** via declarative YAML blueprints in `authentik/blueprints/`.
   - Application tiles must be registered in the Authentik dashboard with verified CDN icons (`https://cdn.jsdelivr.net/gh/selfhst/icons/png/<name>.png`).

7. **Component Sustainability & Registry Pinning (Rule 7)**:
   - NEVER use `:latest` image tags. Always query container registries to pin the exact, latest stable version tag or digest.

8. **Lightness & Portability (Rule 8)**:
   - The stack is designed to run self-contained on a single machine (laptop, VM, homelab).
   - CPU-friendly models (`lfm2.5-thinking:1.2b`) are prioritized for out-of-the-box operation without requiring GPU hardware.

9. **GitOps-Native & Declarative Selection (Rule 9)**:
   - Only select components configured via mounted YAML/JSON/HCL files.
   - All services must be registered in Gatus GitOps monitoring (`gatus/config.yaml.template`).

10. **Zero-Assumption Versioning & Up-to-Date Official Documentation (Rule 10)**:
    - NEVER deduce, guess, or extrapolate external version tags, action versions (e.g. GitHub Actions `@vX`), container tags, or API syntax from memory.
    - ALWAYS formally verify the exact, released version tag and syntax in official documentation or repository releases (via web search or API tools) BEFORE writing or modifying any configuration/workflow file.
    - Proactively research and identify edge cases (e.g. reverse-proxy path rewrites, WebSocket origin checks, trailing slashes in OIDC discovery, forward-auth header mappings, CORS, health check probes) to eliminate runtime surprises.

11. **Vanilla Runners & Pure Containerized CI (Rule 11)**:
    - CI runners MUST remain 100% vanilla, standard, and unpolluted (`myoung34/github-runner:latest`).
    - NEVER install ad-hoc tools, CLI binaries, or packages (`apt-get`, `pip`, curl-to-bin) into the runner image or host.
    - All CI jobs, linters, validators, and scanners MUST run inside isolated, versioned Docker containers declared with `container: <image>:<tag>` in workflow YAML files.
    - Local Makefiles must use container fallbacks (`docker run`) so developer workstations require zero extra tool installations.

---

## 🛡️ Infrastructure Change Management & CAB Protocol

Before applying ANY change to configurations, code, scripts, docker-compose, or running containers:

### 📋 Mandatory Pre-Change CAB Checklist
1. **Scope & Exact Changes**: Detail exact files, lines, and services being touched.
2. **Impact & Risk Analysis (Runtime & Production)**:
   - Identify all directly and indirectly affected services.
   - Assess risks to active workloads, hot-reloading side-effects, and file dependencies.
   - *Special Directive*: **NEVER restart, recreate, or interrupt `litellm` without explicit user permission.**
3. **Execution Sequencing (Zero-Downtime Rule)**:
   - If a file mounted in a live container is being modified to reference a new dependency (e.g. `include:` in LiteLLM or targets in Prometheus), inject the dependency into the running container (`docker cp`) **BEFORE** editing the monitored configuration on the host.
   - Never assume disk state matches live container state.
4. **Post-Change Verification Plan**:
   - Always verify live service logs (`docker compose logs <service> --since=30s`) immediately after any change.
   - Verify health endpoints and ensure zero exceptions or Tracebacks.
5. **Rollback Plan**:
   - Have an immediate rollback command/action ready if anything fails.

---

## 🧩 Adding a New Application Workflow (`ADDING_AN_APPLICATION.md`)

When adding a new service, follow the 7-step process:
1. **Audit & Pin Version**: Find latest stable release tag.
2. **Consult & Approve**: Get user sign-off on name, subdomain, port, and auth model.
3. **Docker & Secrets as Code**: Add service to `docker-compose.yml`, generate secrets in `setup.sh` + `.env.example`.
4. **Traefik Routing & Authentik SSO**: Configure Traefik labels + YAML Blueprint in `authentik/blueprints/`.
5. **Cloudflare Zero Trust IaC**: Add subdomain to `cloudflare/variables.tf` and apply via Terraform.
6. **Gatus GitOps Monitoring**: Add health check endpoint in `gatus/config.yaml.template`.
7. **Validation & Smoke Test**: Add test in `scripts/smoke_test.py`, update `README.md`, commit using Conventional Commits.

---

## 🌍 Extension Points & Local Privacy Isolation

To allow developers to customize their stack without leaking private configurations to Git:
- **Prometheus Scrape Targets**: Put private targets in `prometheus/targets.d/*.yml` (gitignored).
- **Gatus Health Endpoints**: Put private/external monitoring endpoints in `gatus/endpoints.d/*.yaml` (gitignored).
- **LiteLLM Models**: Put private/external models in `litellm/custom_models.yaml` and run `git update-index --assume-unchanged litellm/custom_models.yaml`.
- **Docker Overrides**: Put local developer container overrides in `docker-compose.override.yml` (gitignored).

---

## 📜 Documentation & Commit Standards

- **Language**: All public documentation, code comments, and scripts must be in **English** (enforced by `make no-french` in CI).
- **Commit Format**: Follow [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`, `refactor:`, `chore:`).
- **Documentation Integrity**: Keep `README.md`, `ADDING_AN_APPLICATION.md`, and service READMEs up to date with all architectural changes.
