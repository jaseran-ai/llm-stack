# Contributing to LLM Stack

Thanks for your interest in contributing. This project follows a strict "Configuration as Code"
philosophy: the entire stack must be reproducible from a clean clone with a single command, with
no manual setup and no hardcoded secrets. Please read this guide before opening a pull request.

---

## Getting Started

```bash
git clone https://github.com/jaseran-ai/llm-stack.git
cd llm-stack
./setup.sh
```

`setup.sh` generates all secrets, hydrates every configuration template, and starts the full
stack. See the main [`README.md`](README.md) for details on domain detection, generated files,
and the full tool catalog.

To validate that everything works end to end:

```bash
./smoke_test.sh
```

This runs a full functional audit (SSO, RBAC, guardrails, observability) against the live stack
and should report `22/22` on a healthy deployment.

---

## Continuous Integration & Local Checks

Every push and pull request runs [`.github/workflows/ci.yml`](.github/workflows/ci.yml): it
validates `docker-compose.yml`, lints every shell script and YAML file, checks that no relative
Markdown link is broken, guards against reintroducing French text (this project's
documentation and scripts were fully translated to English for its international release), and
scans every image declared in `docker-compose.yml` for known CRITICAL/HIGH CVEs with
[Trivy](https://trivy.dev/) (one job per image, matrix computed dynamically from
`docker compose config --images` so a new service is covered automatically). CI
does not run `smoke_test.sh` itself: shared GitHub Actions runners have unpredictable, limited
CPU performance for real LLM inference (confirmed empirically to be dramatically slower and less
consistent than a real deployment machine — see [`ollama/README.md`](ollama/README.md)'s "CPU
Thread Pinning" section) and no bounded timeout would reliably prevent a stuck run from tying up
CI minutes for hours. `smoke_test.sh` is meant to be run manually against a real deployment, as
shown above.

CI runs on GitHub-hosted runners only (`ubuntu-24.04`); every tool comes from a digest-pinned image
declared in the `Makefile`. Changes reach `main` through pull requests that pass every CI check
(see the ruleset in [`.github/rulesets/main.json`](.github/rulesets/main.json)).

You can run the same checks locally before pushing:

```bash
make lint          # runs every check below, same as .github/workflows/ci.yml
make shellcheck
make yamllint
make markdown-links
make no-french
make compose-validate
make actions-security  # actionlint + zizmor audit of .github/ (ZIZMOR_ONLINE=1 GH_TOKEN=... for online audits)
make trivy          # not part of "make lint" (pulls & scans every image, much slower);
                     # requires the trivy CLI: https://aquasecurity.github.io/trivy/latest/getting-started/installation/
```

Run `make help` for the full list of targets, including stack lifecycle shortcuts
(`make up`, `make down`, `make restart`, `make ps`, `make logs`, `make smoke-test`) and
backup/restore (`make backup`, `make backups`, `make restore BACKUP=<timestamp>`).

[Dependabot](.github/dependabot.yml) also opens a weekly pull request for any outdated Docker
image or GitHub Action, in support of the "no deprecated tools" governance rule.

Every service in `docker-compose.yml` uses a literal `image: name:tag` (or `name@sha256:digest`)
reference, on purpose: Dependabot's docker-compose ecosystem cannot resolve `${VAR}` references
against a `.env` file (confirmed against its parser source - it silently skips any image field
that isn't a literal string, with no default value fallback). If you add a new service, use a
literal image reference too, not an environment variable, so Dependabot can actually track it.

---

## Project Principles

This project follows the governance rules defined in [`.gemini/rules.md`](.gemini/rules.md).
In short:

- **No unilateral structural changes** — significant changes (network, security, schemas,
  architecture) should be discussed before being applied.
- **Everything as code** — no manual, undocumented fixes applied directly to a running
  container or database. If a fix is needed, it belongs in a template, a script, or
  `docker-compose.yml`.
- **No hardcoded secrets, ever** — secrets are generated dynamically by `setup.sh` and injected
  through `.env`. Never commit a real secret, even temporarily.
- **Prove it works** — a change is not considered complete until it has been verified with a
  real test (a `curl` request, an HTTP status code, a script output), not just a visual check.
- **Keep dependencies current** — only add Docker images, libraries, or tools that are actively
  maintained and not deprecated.

---

## Adding a New Application

If you want to add a new service to the stack, follow the complete guide in
[`ADDING_AN_APPLICATION.md`](ADDING_AN_APPLICATION.md). It covers:

- Docker Compose service declaration and secret generation
- Traefik reverse proxy routing and Authentik SSO integration
- Authentik Application Dashboard metadata (launch URL, icon, description)
- The empirical validation and documentation steps required before a change is considered done

---

## Code of Conduct & Security

- This project is governed by the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.
- To report security vulnerabilities privately, please review our [Security Policy](SECURITY.md).

---

## Commit Messages

This project uses [Conventional Commits](https://www.conventionalcommits.org/):

```
type(scope): short description

Longer explanation if needed - what changed, why, and how it was verified.
```

Common types: `feat`, `fix`, `refactor`, `docs`, `chore`, `security`.

Example:
```
fix(authentik): add /dashboard path to Qdrant application launch URL
```

---

## Pull Requests

- Keep changes focused and well-scoped.
- Update the relevant documentation (`README.md`, a service's own `README.md`, or `ROADMAP.md`)
  as part of the same change, not as a follow-up.
- Include evidence that the change works (test output, command results) in the PR description.
- Never commit generated or secret files (`.env`, `litellm/litellm.env`, and so on) — they are already covered by `.gitignore`.
