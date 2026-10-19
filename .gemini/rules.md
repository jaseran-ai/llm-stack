# Universal AI Assistant Governance Directives

These rules apply permanently to every pair-programming, development, and architecture session.

---

### 1. Prior Consultation & Alignment (Zero Unilateral Decisions)
- **Principle**: Never apply structural changes (network configuration files, databases, security, schemas, or architecture) without prior consultation.
- **Requirement**: The assistant must lay out the diagnosis, present the facts and technical choices along with their impact, and then **wait for explicit user approval** before executing anything.

---

### 2. Absolute Reproducibility, "As Code" (No Manual Bricolage / No Manual Fixes)
- **Principle**: Every project, service, or piece of infrastructure must be rebuildable from scratch, deterministically, using versioned scripts and templates.
- **Prohibited**: Manual live patching of any kind (monkey-patching, manual SQL queries against a running database, direct edits inside a running container).

---

### 3. Automated Empirical Proof (Demonstrate with Facts)
- **Principle**: A change or feature is never considered "done" until it has been validated by an autonomous, automated test.
- **Requirement**: Run real tests (Python/Bash scripts, curl requests, unit/integration tests) and provide raw proof of success (HTTP status codes, logs, API responses).

---

### 4. Strict Preservation of Data & Volumes
- **Principle**: User data and persistent volumes are sacred.
- **Prohibited**: Running destructive commands (`docker compose down -v`, `rm -rf` on data, database purges) without explicit authorization.
- **Best practice**: For any test that requires a clean state, create an isolated Docker project/environment with dedicated test volumes.

---

### 5. Strict Secret Management & Zero Fallback Secrets
- **Principle**: No secret, password, or API key should ever be hardcoded or fall back to a static default value in code or scripts.
- **Requirement**: Generate cryptographic secrets dynamically and propagate them securely through environment files (`.env`) and explicit environment variables.

---

### 6. End-to-End System Architect Mindset
- **Principle**: Never treat a symptom in isolation or address it partially.
- **Requirement**: Address the entire value chain:
  1. **Centralized security & authentication**
  2. **Provisioning & configuration as code**
  3. **Monitoring & observability**
  4. **Automated testing & reproducibility**

---

### 7. Component Longevity & Docker Image Version Verification
- **Principle**: Never introduce an obsolete, deprecated, or outdated component or Docker image tag.
- **Requirement**: Before proposing or modifying any Docker image in `docker-compose.yml`, actively query the container registry API (Docker Hub, GitHub Container Registry, Quay, etc.) to verify and use the exact **latest stable release version tag** (avoiding unverified assumptions, stale versions, or untagged floats).

---

### 8. Lightness & Portability First (Top Priority for This Open Source Project)
- **Principle**: This project is open source and must run on the widest possible range of machines (laptops, small VMs, CI runners) with the smallest possible footprint. Between two options of otherwise comparable merit, always favor the lighter, more portable one.
- **Requirement**: When choosing or comparing a Docker image, dependency, or architecture, measure and report the real, uncompressed on-disk size (`docker inspect --format '{{.Size}}'`, not marketing claims like "slim") before recommending a change. A "lighter" label is not sufficient proof by itself.
- **Trade-off discipline**: A size reduction that requires losing self-containment (e.g. reintroducing an external hardware/service dependency, or requiring runtime network access to fetch models/weights on first use) must be flagged explicitly as a portability regression, even if it saves disk space.

---

### 9. Declarative GitOps-Native & Database-Agnostic Selection First
- **Principle**: When choosing new tools or services to add to the stack, always prioritize **GitOps-native tools** configured 100% via declarative configuration files (`YAML`, `HCL`, `JSON`) mounted directly into containers over "GUI-first" tools that require custom database seeding scripts to achieve automation.
- **Requirement**: Always run a preliminary architectural filter before proposing any new tool:
  1. *Is it 100% declarative via native configuration files without custom DB seeding workarounds?*
  2. *Is it compatible with the existing PostgreSQL database or stateless out of the box?*
  3. *Does it avoid GUI-first setup wizards entirely?*

