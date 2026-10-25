# AI Agent Rules & Operational Guidelines — `llm-stack`

This document is the single source of the authoritative, binding rules and governance for every AI assistant and automated agent working in this repository. Keep all agent instructions here; tool-specific files only point to this one:

| Tool | How it loads these rules |
| :--- | :--- |
| Cursor, OpenCode, Codex and other `AGENTS.md`-aware agents | Read `AGENTS.md` natively |
| Claude Code | `CLAUDE.md` imports it (`@AGENTS.md`) |
| Gemini CLI | `.gemini/settings.json` sets `context.fileName` to `AGENTS.md` |

---

## 🏛️ Core Architecture Governance Rules

1. **Prior Consultation & Approval (Rule 1)**:
   - NEVER make unilateral architectural, networking, database schema, or security changes.
   - Always present a clear diagnostic, the facts, and the technical options with their impact, then wait for explicit user confirmation before proceeding.

2. **Absolute Reproducibility as Code (Rule 2)**:
   - The entire stack must be 100% reproducible from a clean clone via `./setup.sh`.
   - NO manual GUI clicks, uncommitted DB edits, or opaque manual fixes. Everything belongs in versioned templates, scripts, or `docker-compose.yml`.
   - NO live patching of any kind: no monkey-patching, no manual SQL against a running database, no direct edits inside a running container.

3. **Automated Empirical Validation — "Prove It Works" (Rule 3)**:
   - A task is NEVER done based on intent or assumption alone.
   - Every change must be validated with raw proof: HTTP status codes, curl outputs, database queries, live service logs, or `./smoke_test.sh` / `python3 scripts/smoke_test.py`.

4. **Strict Preservation of Data & Volumes (Rule 4)**:
   - NEVER run `docker compose down -v`, `rm -rf` on data directories, or destructive database commands without explicit user instruction.
   - When a test needs a clean state, use an isolated Docker Compose project with dedicated test volumes (see `uat/`) instead of the live stack.

5. **Zero Hardcoded Secrets & Zero Fallback Defaults (Rule 5)**:
   - NEVER use fallback syntax in `docker-compose.yml` (e.g. `${MY_SECRET:-default}` is FORBIDDEN; use bare `${MY_SECRET}`).
   - Secrets are generated dynamically in `setup.sh` (`openssl rand -hex 32`), stored in Vault KV v2, and rendered into memory-backed tmpfs (`vault/secrets_ram/`).

6. **End-to-End Architectural Integrity & Unified SSO (Rule 6)**:
   - Never treat a symptom in isolation or address it partially: every change covers the whole chain, i.e. centralized security and authentication, provisioning and configuration as code, monitoring and observability, and automated tests.
   - Authentik is the single source of truth for identity and access.
   - New services must use either **Pattern A (Forward-Auth)** or **Pattern B (Native OIDC)** via declarative YAML blueprints in `authentik/blueprints/`.
   - Application tiles must be registered in the Authentik dashboard with verified CDN icons (`https://cdn.jsdelivr.net/gh/selfhst/icons/png/<name>.png`).

7. **Component Sustainability & Registry Pinning (Rule 7)**:
   - NEVER introduce an obsolete, deprecated, or unmaintained component, and NEVER use `:latest` or other floating tags.
   - Before proposing or changing an image, query the registry API (Docker Hub, GHCR, Quay, ...) and pin the exact latest stable version tag and its digest.

8. **Lightness & Portability (Rule 8)**:
   - The stack is designed to run self-contained on a single machine (laptop, VM, homelab). Between two options of otherwise comparable merit, always favor the lighter, more portable one.
   - CPU-friendly models (`lfm2-1.2b-rag`) are prioritized for out-of-the-box operation without requiring GPU hardware.
   - Before recommending an image, dependency, or architecture for being lighter, measure and report its real uncompressed size (`docker image inspect --format '{{.Size}}'`); a "slim" label is not proof.
   - Flag explicitly as a portability regression any size gain that costs self-containment (an external hardware or service dependency, or network access at runtime to fetch models or weights).

9. **GitOps-Native & Declarative Selection (Rule 9)**:
   - Only select components configured via mounted YAML/JSON/HCL files. Before proposing a new tool, check that it is:
     1. fully declarative through native configuration files, without custom database seeding workarounds;
     2. compatible with the existing PostgreSQL instance, or stateless;
     3. free of GUI-first setup wizards.
   - All services must be registered in Gatus GitOps monitoring (`gatus/config.yaml.template`).

10. **Zero-Assumption Versioning & Up-to-Date Official Documentation (Rule 10)**:
    - NEVER deduce, guess, or extrapolate external version tags, action versions (e.g. GitHub Actions `@vX`), container tags, or API syntax from memory.
    - ALWAYS formally verify the exact, released version tag and syntax in official documentation or repository releases (via web search or API tools) BEFORE writing or modifying any configuration/workflow file.
    - Proactively research and identify edge cases (e.g. reverse-proxy path rewrites, WebSocket origin checks, trailing slashes in OIDC discovery, forward-auth header mappings, CORS, health check probes) to eliminate runtime surprises.

11. **GitHub-Hosted Runners & Hardened, Containerized CI (Rule 11)**:
    - The repository is public: CI MUST run on GitHub-hosted runners pinned to an explicit image (`runs-on: ubuntu-24.04`, never `ubuntu-latest`). Self-hosted runners are FORBIDDEN, since any fork pull request could execute code on them.
    - NEVER install ad-hoc tools, CLI binaries, or packages into the runner; the only exception is hash-pinned test dependencies (`pip install --require-hashes`).
    - Linters, validators, and scanners run from version- and digest-pinned images through the Makefile (`USE_CONTAINERS=1` in CI) or a pinned `container:` image; local Makefile targets keep `docker run` fallbacks so workstations need no extra tools.
    - Workflows MUST pass `make actions-security` (actionlint + zizmor): actions pinned to full commit SHAs, `permissions: {}` at workflow level with least privilege per job, `persist-credentials: false` on checkout, no `${{ }}` expressions inside `run:` scripts (pass them through `env:`), no `pull_request_target`.
    - The `main` branch is protected by `.github/rulesets/main.json` (applied with `make github-harden`): pull requests and all CI checks required, no force push or deletion. Keep its required checks equal to the CI job names.

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
- **No AI Attribution**: Commits and pull requests carry no AI-assistant attribution (no `Co-Authored-By` trailer for an assistant, no "Generated with ..." footer).
- **Merging**: Changes reach `main` only through pull requests merged with **rebase** (enforced by the ruleset), which keeps each commit's original author.
- **Documentation Integrity**: Keep `README.md`, `ADDING_AN_APPLICATION.md`, and service READMEs up to date with all architectural changes.
