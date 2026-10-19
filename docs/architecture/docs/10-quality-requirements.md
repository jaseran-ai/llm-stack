# 10. Quality Requirements

This section defines the quality tree and concrete quality scenarios for the LLM Stack based on ISO 25010.

---

## 10.1 Quality Tree

```text
Quality Requirements
├── 1. Security & Privacy (Weight: Critical)
│   ├── Confidentiality: In-memory secrets (tmpfs 0700/0600), zero disk persistence.
│   ├── Integrity: Mandatory internal TLS verification, no bypass flags, signed SigV4 S3.
│   ├── Authentication: Authentik single source of truth, Forward-Auth and OIDC RBAC.
│   └── Privacy: In-flight secret and PII redaction, AES-256-GCM encrypted tokenization.
├── 2. Reproducibility & Portability (Weight: High)
│   ├── Configuration as Code: 100% reproducible via ./setup.sh on clean checkout.
│   ├── CPU-Friendly Inference: Bundled Ollama runs without requiring NVIDIA GPU hardware.
│   └── Multi-Arch Pinning: Exact multi-arch SHA256 digests across all Compose images.
├── 3. Reliability & Fault Tolerance (Weight: High)
│   ├── Model Fallback: Automatic cascade to secondary LLMs on rate limits or API errors.
│   ├── Automated Probing: Gatus GitOps health monitoring with Alertmanager alerting.
│   └── Atomic Backups: Cryptographically verified, isolated pg_dumpall and volume archives.
└── 4. Observability & Performance (Weight: Medium)
    ├── Latency & Tracing: Microsecond-precision Langfuse spans and token consumption metrics.
    └── System Monitoring: Prometheus time-series scraping and Grafana executive dashboards.
```

---

## 10.2 Quality Scenarios

| Scenario ID | Quality Attribute | Stimulus / Trigger | Architecture Response & Measurement |
|---|---|---|---|
| `QS-SEC-01` | **Confidentiality** | Malicious process executes inside an unprivileged container. | Cannot read secrets from other containers: `/vault/secrets_ram` is an isolated tmpfs mount with mode `0700`. |
| `QS-SEC-02` | **Data Privacy** | User prompt contains sensitive API keys or credit card numbers. | Betterleaks Presidio intercepts the stream in < 30ms, replacing secrets with surrogate tokens before forwarding to the LLM. |
| `QS-REL-01` | **Fault Tolerance** | An upstream cloud LLM provider returns `HTTP 429 Too Many Requests`. | LiteLLM automatically reroutes the completion to the next configured fallback model in < 250ms with zero client exception. |
| `QS-OPS-01` | **Reproducibility** | Fresh clone executed on an offline or clean developer workstation. | `./setup.sh` generates all cryptographic secrets, initializes databases, and achieves 28/28 smoke test pass rate in < 5 minutes. |
