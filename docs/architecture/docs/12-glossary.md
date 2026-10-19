# 12. Glossary

This section references the canonical **Single Source of Truth** for technical terminology and component definitions.

For the complete, maintained glossary, refer to the root technical glossary:

> **Canonical Source**: [`docs/shared/GLOSSARY.md`](https://github.com/jaseran-ai/llm-stack/blob/main/docs/shared/GLOSSARY.md)

---

## Key Platform Definitions

* **Authentik**: Unified Identity Provider (IdP) providing Single Sign-On (SSO) and Role-Based Access Control (RBAC).
* **Betterleaks**: High-throughput Go and Python PII and secret redaction engine with reversible vaulted tokenization.
* **Forward-Auth (Pattern A)**: Reverse proxy authentication pattern delegating access verification to Authentik before forwarding requests upstream.
* **Native OIDC (Pattern B)**: Standard OpenID Connect OAuth2 authorization code flow implemented directly inside modern services.
* **LiteLLM**: Unified OpenAI-compatible proxy gateway managing load balancing, spend quotas, and model fallbacks.
* **Langfuse**: Open-source LLMOps observability platform for tracing prompts, evaluations, latencies, and token costs.
* **SeaweedFS**: High-speed, Apache 2.0 licensed S3 object storage providing AWS SigV4 signed access and granular IAM policies.
* **Vault**: HashiCorp Vault managing KV v2 secret paths and rendering environment files into memory-backed `tmpfs` mounts.
