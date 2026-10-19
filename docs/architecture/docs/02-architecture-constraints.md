# 2. Architecture Constraints

This section documents the technical, organizational, and regulatory constraints governing the development and deployment of the LLM Stack.

---

## 2.1 Technical Constraints

* **Single-Node Containerization**: The architecture is designed to run self-contained within Docker Compose on a single Linux machine. Multi-node Kubernetes clustering is out of scope to preserve homelab and edge portability.
* **CPU-First Out-of-the-Box Operation**: While GPU passthrough (`nvidia-container-toolkit`) is supported for acceleration, the default baseline configuration must operate reliably on standard x86_64 / arm64 CPUs using quantized GGUF weights.
* **100% Declarative Configuration as Code (CaC)**: All configurations must reside in version-controlled templates, declarative blueprints, or Terraform files. Manual adjustments in web consoles are strictly forbidden (governance Rule 2).
* **Zero Hardcoded Secrets & Zero Fallback Defaults**: Secrets must be dynamically provisioned at runtime into HashiCorp Vault KV v2 and rendered into memory (`tmpfs`). Syntax like `${SECRET:-default}` is strictly forbidden in Compose definitions.
* **Registry Pinning & Digest Immutability**: Container images must be pinned to immutable SHA256 digests or exact semantic version tags. Using `:latest` is forbidden in production files (governance Rule 7).

---

## 2.2 Organizational & Governance Constraints

* **Strict English Language Standard**: All public documentation, code comments, commit messages, and script output must be in English (enforced in CI via `make no-french`).
* **Prior Consultation & CAB Protocol**: No unilateral architectural, networking, database schema, or security change can be made without presenting a diagnostic and rollback plan and receiving explicit authorization (governance Rule 1).
* **Zero Downtime for Core Proxy (`litellm`)**: The core LLM routing gateway must never be restarted, recreated, or interrupted without explicit permission.
* **Automated Empirical Validation**: A task is never complete based on assumptions; raw proof of HTTP 200, clean logs, and 100% smoke test pass rate (`./smoke_test.sh`) is mandatory (governance Rule 3).

---

## 2.3 Conventions

* **Commit Messages**: Conventional Commits specification (`feat:`, `fix:`, `docs:`, `chore:`, `refactor:`).
* **Documentation Methodology**:
  - User and Integrator guides: **Diátaxis framework** (`docs/user/`).
  - Architecture and Engineering documentation: **arc42 + C4 + MADR** (`docs/architecture/`).
