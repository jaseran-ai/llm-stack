SHELL := /bin/bash
.DEFAULT_GOAL := help

# Detect how to invoke yamllint: prefer the plain binary, fall back to `python3 -m yamllint`
# (how it gets installed here and in CI when pulled in via pip without a console script on PATH).
YAMLLINT := $(shell command -v yamllint 2>/dev/null || echo "python3 -m yamllint")
PYTHON_TEST_IMAGE := python:3.14.7-bookworm@sha256:ecac9e212daacda8a702eae372fceebc0ee36f5805abe087880367e8d061fa5b
YAMLLINT_IMAGE := cytopia/yamllint:1@sha256:596fb19eb71e55ba5b2fa56d8c18a615ec82adc8d3bf2d73918cb78c8f3240fb
TRIVY_IMAGE := aquasec/trivy:0.72.0@sha256:cffe3f5161a47a6823fbd23d985795b3ed72a4c806da4c4df16266c02accdd6f
SHELLCHECK_IMAGE := koalaman/shellcheck:v0.11.0@sha256:61862eba1fcf09a484ebcc6feea46f1782532571a34ed51fedf90dd25f925a8d
GITLEAKS_IMAGE := zricethezav/gitleaks:v8.30.1@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f
TERRAFORM_IMAGE := hashicorp/terraform:1.10.5@sha256:679ac5e095bf550bc726742cd12efa6050f0913080df479fdabfeb202953af28
ZIZMOR_IMAGE := ghcr.io/zizmorcore/zizmor:1.31.1@sha256:42d409dbb851d4c5d35a058cf042b828bea1e3f2884378c526eb0974780e18d9
ACTIONLINT_IMAGE := rhysd/actionlint:1.7.12@sha256:b1934ee5f1c509618f2508e6eb47ee0d3520686341fec936f3b79331f9315667

# Run the pinned Python image as the invoking user: git accepts the mounted checkout
# ("dubious ownership" otherwise) and no root-owned files (e.g. __pycache__) are left behind.
PYTHON_RUN := docker run --rm --user "$$(id -u):$$(id -g)" -e HOME=/tmp -v "$$(pwd):/data" -w /data $(PYTHON_TEST_IMAGE)

# USE_CONTAINERS=1 ignores locally installed tools and always runs the pinned images above.
# CI sets it so results never depend on what a runner image happens to ship.
USE_CONTAINERS ?= 0

.PHONY: help
help: ## Show this help
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

## --- Checks (mirrors .github/workflows/ci.yml) -----------------------------

.PHONY: lint
lint: shellcheck yamllint markdown-links no-french compose-validate script-tests gitleaks terraform-validate actions-security ## Run every CI check locally (same as .github/workflows/ci.yml)
	@echo "All checks passed."

.PHONY: terraform-validate
terraform-validate: ## Validate Cloudflare Terraform files
	@if [ "$(USE_CONTAINERS)" != "1" ] && command -v terraform >/dev/null 2>&1; then \
		(cd cloudflare && terraform init -backend=false -input=false >/dev/null && terraform validate); \
	else \
		docker run --rm --user "$$(id -u):$$(id -g)" -e HOME=/tmp -v "$$(pwd)/cloudflare:/data" -w /data $(TERRAFORM_IMAGE) init -backend=false -input=false >/dev/null && \
		docker run --rm --user "$$(id -u):$$(id -g)" -e HOME=/tmp -v "$$(pwd)/cloudflare:/data" -w /data $(TERRAFORM_IMAGE) validate; \
	fi

.PHONY: gitleaks
gitleaks: ## Scan repository for hardcoded secrets using Gitleaks (Docker-native)
	@if [ "$(USE_CONTAINERS)" != "1" ] && command -v gitleaks >/dev/null 2>&1; then \
		gitleaks detect --source=. --config=.gitleaks.toml --no-git --redact --verbose; \
	else \
		docker run --rm -v "$$(pwd):/path" -w /path $(GITLEAKS_IMAGE) detect --source=/path --config=/path/.gitleaks.toml --no-git --redact --verbose; \
	fi

.PHONY: actions-security
actions-security: ## Audit GitHub Actions workflows (zizmor security audit + actionlint)
	@docker run --rm -v "$$(pwd):/repo:ro" -w /repo $(ACTIONLINT_IMAGE) -no-color
	@# GH_TOKEN (optional, read-only) enables zizmor's online audits (known-vulnerable
	@# actions, impostor commits); without it only the offline audits run.
	@docker run --rm -e GH_TOKEN -v "$$(pwd):/repo:ro" -w /repo $(ZIZMOR_IMAGE) \
		--format plain $$( [ -n "$${GH_TOKEN:-}" ] || echo --offline ) .github
	@echo "GitHub Actions workflows: no actionlint or zizmor findings."

.PHONY: github-harden
github-harden: ## Apply GitHub security settings and the main ruleset (REPO=owner/name, DRY_RUN=1 to preview)
	@./scripts/github_harden.sh $(if $(filter 1,$(DRY_RUN)),--dry-run,) $(REPO)

.PHONY: install-hooks
install-hooks: ## Install Git pre-commit hook for automated secret protection
	@set -eu; \
		hooks_dir="$$(git rev-parse --path-format=absolute --git-path hooks)"; \
		mkdir -p "$$hooks_dir"; \
		cp scripts/git-hooks/pre-commit "$$hooks_dir/pre-commit"; \
		chmod +x "$$hooks_dir/pre-commit"; \
		echo "Pre-commit hook installed in $$hooks_dir/pre-commit"

.PHONY: shellcheck
shellcheck: ## Lint lifecycle and UAT shell scripts with shellcheck
	@if [ "$(USE_CONTAINERS)" != "1" ] && command -v shellcheck >/dev/null 2>&1; then \
		shellcheck setup.sh start.sh stop.sh restart.sh smoke_test.sh scripts/*.sh scripts/tests/*.sh scripts/uat/*.sh */provision.sh traefik/scripts/*.sh; \
	else \
		docker run --rm -v "$$(pwd):/mnt" -w /mnt $(SHELLCHECK_IMAGE) setup.sh start.sh stop.sh restart.sh smoke_test.sh scripts/*.sh scripts/tests/*.sh scripts/uat/*.sh */provision.sh traefik/scripts/*.sh; \
	fi

.PHONY: yamllint
yamllint: ## Lint every YAML file (see .yamllint for the rule config)
	@if [ "$(USE_CONTAINERS)" != "1" ] && command -v yamllint >/dev/null 2>&1; then \
		yamllint .; \
	elif [ "$(USE_CONTAINERS)" != "1" ] && python3 -m yamllint --version >/dev/null 2>&1; then \
		python3 -m yamllint .; \
	else \
		docker run --rm -v "$$(pwd):/data" -w /data $(YAMLLINT_IMAGE) .; \
	fi

.PHONY: markdown-links
markdown-links: ## Check that every relative Markdown link resolves to a real file
	@if [ "$(USE_CONTAINERS)" != "1" ] && command -v python3 >/dev/null 2>&1; then \
		python3 .github/scripts/check_markdown_links.py; \
	else \
		$(PYTHON_RUN) python3 .github/scripts/check_markdown_links.py; \
	fi

.PHONY: no-french
no-french: ## Guard against reintroducing French text (repo was fully translated to English)
	@if [ "$(USE_CONTAINERS)" != "1" ] && command -v python3 >/dev/null 2>&1; then \
		python3 .github/scripts/check_no_french.py; \
	else \
		$(PYTHON_RUN) python3 .github/scripts/check_no_french.py; \
	fi

.PHONY: compose-validate
compose-validate: ## Validate Compose files against placeholder secrets
	@tmpenv=$$( [ -f .env ] && echo 1 || echo 0 ); \
	[ -f .env ] || cp .env.example .env; \
	if [ ! -f traefik/traefik.yml ] || [ ! -f traefik/dynamic.yml ]; then \
		python3 traefik/scripts/hydrate_traefik.py >/dev/null 2>&1 || true; \
	fi; \
	mkdir -p coredns; \
	[ -f coredns/Corefile ] || cp coredns/Corefile.template coredns/Corefile 2>/dev/null || touch coredns/Corefile; \
	mkdir -p litellm; \
	[ -f litellm/litellm.env ] || touch litellm/litellm.env; \
	mkdir -p vault/secrets_ram; \
	created_secret_envs=""; \
	for secret_env in open-webui litellm langfuse grafana qdrant chouse-ui betterleaks; do \
		secret_path="vault/secrets_ram/$$secret_env.env"; \
		if [ ! -f "$$secret_path" ]; then touch "$$secret_path"; created_secret_envs="$$created_secret_envs $$secret_path"; fi; \
	done; \
	status=0; \
	docker compose config -q && echo "docker-compose.yml is valid." || status=$$?; \
	if [ "$$status" = "0" ]; then \
		UAT_WORKTREE_GID="$$(id -g)" docker compose -f docker-compose.yml \
			-f uat/ollama-model-cache.override.yml --profile provisioning config -q || status=$$?; \
	fi; \
	if [ "$$status" = "0" ]; then \
		docker compose --profile provisioning config --format json | \
			python3 .github/scripts/check_startup_graph.py || status=$$?; \
	fi; \
	[ -n "$$created_secret_envs" ] && rm -f $$created_secret_envs; \
	if [ "$$tmpenv" = "0" ]; then rm -f .env; fi; \
	exit "$$status"

.PHONY: authentik-tests
authentik-tests: ## Run Authentik provisioning and repository validator unit tests
	@if [ "$(USE_CONTAINERS)" != "1" ] && command -v python3 >/dev/null 2>&1; then \
		python3 -m unittest discover -s authentik/tests -v && \
		python3 -m unittest discover -s .github/scripts -p 'test_*.py' -v; \
	else \
		$(PYTHON_RUN) sh -c 'python3 -m pip install --quiet --user --no-cache-dir \
			--require-hashes -r .github/requirements-tests.txt && \
			python3 -m unittest discover -s authentik/tests -v' && \
		$(PYTHON_RUN) \
			python3 -m unittest discover -s .github/scripts -p 'test_*.py' -v; \
	fi

.PHONY: vault-tests
vault-tests: ## Run Vault provisioning unit tests
	@if [ "$(USE_CONTAINERS)" != "1" ] && command -v python3 >/dev/null 2>&1; then \
		python3 -m unittest discover -s vault/tests -v; \
	else \
		$(PYTHON_RUN) \
			python3 -m unittest discover -s vault/tests -v; \
	fi

.PHONY: python-automation-tests
python-automation-tests: ## Run shared HTTP client and application provisioning unit tests
	@if [ "$(USE_CONTAINERS)" != "1" ] && command -v python3 >/dev/null 2>&1; then \
		python3 -m unittest discover -s scripts/tests -p 'test_*.py' -v; \
	else \
		$(PYTHON_RUN) \
			python3 -m unittest discover -s scripts/tests -p 'test_*.py' -v; \
	fi

.PHONY: prometheus-tests
prometheus-tests: ## Run Prometheus hydration tests
	@if command -v bash >/dev/null 2>&1; then \
		bash prometheus/tests/test_hydrate_config.sh; \
	else \
		$(PYTHON_RUN) \
			bash prometheus/tests/test_hydrate_config.sh; \
	fi

.PHONY: backup-restore-tests
backup-restore-tests: ## Run Backup/Restore validation and safety tests
	@bash scripts/tests/test_backup_restore.sh

.PHONY: script-tests
script-tests: python-automation-tests authentik-tests vault-tests prometheus-tests backup-restore-tests ## Run every script and startup graph unit test

.PHONY: trivy
trivy: ## Scan every image in docker-compose.yml for CRITICAL/HIGH CVEs (uses trivy CLI or docker run aquasec/trivy)
	@tmpenv=$$( [ -f .env ] && echo 1 || echo 0 ); \
	[ -f .env ] || cp .env.example .env; \
	mkdir -p litellm; \
	[ -f litellm/litellm.env ] || touch litellm/litellm.env; \
	echo "==> Building custom images if any so they can be scanned locally"; \
	docker compose build --quiet; \
	fail=0; \
	if command -v trivy >/dev/null 2>&1; then \
		TRIVY_BIN="trivy"; \
	else \
		TRIVY_BIN="docker run --rm -v /var/run/docker.sock:/var/run/docker.sock -v /tmp/trivy-cache:/root/.cache/ $(TRIVY_IMAGE)"; \
	fi; \
	for image in $$(docker compose config --images | sort -u); do \
		echo "==> Scanning $$image"; \
		exit_code=1; \
		if [ -f .github/trivy-accepted-risk.txt ] && grep -qxF "$$image" .github/trivy-accepted-risk.txt; then \
			exit_code=0; \
		fi; \
		$$TRIVY_BIN image --scanners vuln --severity CRITICAL,HIGH --ignore-unfixed --exit-code $$exit_code "$$image" || fail=1; \
	done; \
	if [ "$$tmpenv" = "0" ]; then rm -f .env; fi; \
	exit $$fail

## --- Stack lifecycle --------------------------------------------------------

.PHONY: setup
setup: ## Run ./setup.sh (generate secrets if needed, hydrate configs)
	./setup.sh

.PHONY: start up
start: ## Start all containers and initialize/unseal services (via ./start.sh)
	./start.sh

up: start ## Alias for 'start'

.PHONY: stop down
stop: ## Stop all containers gracefully (volumes preserved, via ./stop.sh)
	./stop.sh

down: stop ## Alias for 'stop'

.PHONY: restart
restart: ## Gracefully restart the entire stack (via ./restart.sh)
	./restart.sh

.PHONY: ps
ps: ## Show the status of every container
	docker compose ps

.PHONY: logs
logs: ## Follow logs for all containers (Ctrl+C to stop)
	docker compose logs -f

.PHONY: smoke-test
smoke-test: ## Run the full functional smoke test suite against the live stack
	./smoke_test.sh

.PHONY: langfuse-monitor-enable
langfuse-monitor-enable: ## Install and activate the production Langfuse ingestion monitor timer
	@test -f systemd/llm-stack-langfuse-ingestion.service.generated
	@test -f systemd/llm-stack-langfuse-ingestion.timer.generated
	@test -d prometheus/textfile
	@docker compose up -d --no-deps node-exporter
	@SMOKE_ENVIRONMENT=production SMOKE_PROD_LANGFUSE_INGESTION=1 python3 scripts/langfuse_ingestion_monitor.py
	@curl --fail --silent --show-error --request POST http://127.0.0.1:9190/-/reload
	@install -D -m 0644 systemd/llm-stack-langfuse-ingestion.service.generated "$$HOME/.config/systemd/user/llm-stack-langfuse-ingestion.service"
	@install -D -m 0644 systemd/llm-stack-langfuse-ingestion.timer.generated "$$HOME/.config/systemd/user/llm-stack-langfuse-ingestion.timer"
	@systemctl --user daemon-reload
	@systemctl --user enable --now llm-stack-langfuse-ingestion.timer

.PHONY: langfuse-monitor-disable
langfuse-monitor-disable: ## Stop the production Langfuse ingestion monitor timer
	@systemctl --user disable --now llm-stack-langfuse-ingestion.timer
	@rm -f prometheus/textfile/langfuse_ingestion.prom

## --- Isolated UAT ----------------------------------------------------------

.PHONY: uat-preflight
uat-preflight: ## Validate UAT prerequisites without starting containers
	./scripts/uat/preflight.sh

.PHONY: uat-setup
uat-setup: ## Prepare a new disposable isolated UAT run for the configured candidate SHA
	./scripts/uat/setup.sh

.PHONY: uat-start
uat-start: ## Start the isolated DinD UAT stack (requires runtime CAB approval)
	./scripts/uat/start.sh $(SERVICES)

.PHONY: uat-smoke-test
uat-smoke-test: ## Run the smoke suite exclusively against the UAT stack
	./scripts/uat/smoke_test.sh $(TESTS)

.PHONY: uat-status
uat-status: ## Show the isolated DinD daemon and UAT service status
	./scripts/uat/status.sh

.PHONY: uat-stop
uat-stop: ## Stop the current disposable UAT run without deleting it
	./scripts/uat/stop.sh

.PHONY: uat-destroy
uat-destroy: ## Destroy UAT application state while preserving its image cache (requires CAB approval)
	./scripts/uat/destroy.sh

## --- Backup & Restore -------------------------------------------------------

.PHONY: backup
backup: ## Create an encrypted backup; use CONSISTENCY=offline for DR qualification
	./backup.sh --consistency "$(or $(CONSISTENCY),online)"

.PHONY: restore
restore: ## Restore: make restore BACKUP=<timestamp> [COMPONENT=<name>] [ALLOW_LITELLM_RESTART=yes]
	./restore.sh BACKUP=$(BACKUP) COMPONENT=$(COMPONENT)

.PHONY: backups
backups: ## List available local backups
	@find backups -maxdepth 1 -type f -name '*.tar.gz.enc' -printf '%f\n' 2>/dev/null | sort || \
		echo "No backups found in ./backups/ - run 'make backup' first."

## --- Documentation ---------------------------------------------------------

.PHONY: docs-check
docs-check: ## Run all 5 documentation guardrails (strict builds, diagrams, OpenAPI, i18n)
	./docs/scripts/check-docs.sh

.PHONY: docs-build
docs-build: ## Build both User and Architecture documentation sites in strict mode
	docker compose -f docs/compose.yaml run --rm docs-user-build
	docker compose -f docs/compose.yaml run --rm docs-arch-build

.PHONY: docs-diagrams
docs-diagrams: ## Export C4 Structurizr DSL and Mermaid diagrams to SVG
	./docs/scripts/export-diagrams.sh

.PHONY: docs-publish-user
docs-publish-user: ## Package User documentation into an immutable container image
	./docs/publish.sh user

.PHONY: docs-publish-arch
docs-publish-arch: ## Package Architecture documentation into an immutable private container image
	./docs/publish.sh architecture

.PHONY: docs-pages
docs-pages: ## Assemble unified GitHub Pages static documentation site in _site
	./docs/scripts/build-pages.sh
