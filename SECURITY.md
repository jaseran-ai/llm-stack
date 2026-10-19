# Security Policy

The `llm-stack` project takes the security of its infrastructure, models, and data seriously. This document outlines our security policies, defense-in-depth architectural principles, and instructions for reporting vulnerabilities.

---

## 🛡️ Supported Versions

Only the latest release on the `main` branch receives active security updates and vulnerability patches.

| Version / Branch | Supported          |
| ---------------- | ------------------ |
| `main`           | :white_check_mark: |
| `< 1.0.0`        | :x:                |

---

## 🔒 Defense-in-Depth Architecture

The stack is designed with zero-trust and defense-in-depth principles:

1. **Zero Hardcoded Secrets & Memory-Backed Storage**:
   - All cryptographic credentials, database passwords, and API tokens are dynamically generated at setup time via `setup.sh` (`openssl rand`).
   - Secrets are managed and stored encrypted in HashiCorp Vault KV v2.
   - Sidecar rendering projects secrets into memory-backed tmpfs (`vault/secrets_ram/`), ensuring zero plaintext credentials touch persistent disk storage.

2. **Unified Identity & Access Management (SSO & RBAC)**:
   - Authentik acts as the centralized Identity Provider.
   - All user-facing services are strictly gated either via Forward-Auth proxy headers (Pattern A) or native OIDC with asymmetric RS256 token signing (Pattern B).
   - Strict role-based access control enforces administrative privileges (`admins` group vs `users` group).

3. **Isolated Docker Networking**:
   - Databases and backend message brokers (PostgreSQL, ClickHouse, Redis, SeaweedFS master) are confined to the `internal-backend` network and are never exposed to the host network interface.

4. **Continuous Automated Supply Chain Security**:
   - Container images are pinned to immutable multi-arch SHA256 digests.
   - Pull requests and commits are automatically scanned using Gitleaks (secret detection) and Trivy (CVE / vulnerability scanning).

---

## 🚨 Reporting a Vulnerability

If you discover a potential security vulnerability in `llm-stack`:

1. **DO NOT report security vulnerabilities via public GitHub issues, discussions, or pull requests.**
2. Report the vulnerability privately via **[GitHub Private Vulnerability Reporting](https://github.com/jaseran-ai/llm-stack/security/advisories/new)**.
3. Alternatively, you may contact the maintainers directly by emailing: `security@jaseran.ai`.

### What to Include in Your Report

To help us triage and resolve the issue quickly, please include:
- A clear description of the vulnerability and its potential impact.
- Step-by-step reproduction instructions or a minimal Proof of Concept (PoC).
- The affected component, file, or service.
- Your assessment of the severity (CVSS if applicable).

### Response Timeline

- **Acknowledgment**: Within 48 hours of receipt.
- **Triage & Assessment**: Within 5 business days.
- **Patch & Release**: Critical security fixes will be prioritized, released via a dedicated security patch, and credited in the release notes.
