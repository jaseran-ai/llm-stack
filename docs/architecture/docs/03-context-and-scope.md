# 3. Context and Scope

This section defines the external boundaries of the LLM Stack, illustrating how it interacts with external users, cloud networks, and remote AI providers.

---

## 3.1 Business Context

The LLM Stack operates as an autonomous cognitive gateway and self-hosted platform:
* **Inbound Traffic**: Clients and engineers access conversational user interfaces, dashboards, and APIs.
* **Outbound Traffic**: When configured, the platform reaches out to external LLM providers (Anthropic, OpenAI, Hugging Face) through the unified LiteLLM proxy, while preserving local execution capabilities via bundled Ollama.
* **Perimeter Ingress**: Incoming requests are tunneled via Cloudflare Zero Trust, eliminating the need to expose ports 80/443 on the host router.

---

## 3.2 Technical System Context (C4 Context Diagram)

The following diagram illustrates the boundary between users, the LLM Stack, and external networks:

![System Context](@site/docs/c4/svg/structurizr-SystemContext.svg)

---

## 3.3 External Interface Matrix

| Channel / Interface | Direction | Protocol | Security Mechanism | Description |
|---|---|---|---|---|
| **Cloudflare Edge** | Inbound | HTTPS (TLS 1.2+) | DNS CAA + DMARC, edge proxy | External access point for users and webhooks. |
| **Cloudflared Tunnel** | Outbound | Encrypted QUIC / HTTPS | Cloudflare Zero Trust token | Establishes secure connection to Cloudflare edge without port forwarding. |
| **Traefik Reverse Proxy** | Inbound | HTTP / HTTPS (Local SAN) | Forward-Auth middleware, Security headers | Internal traffic routing, TLS termination, and SSO verification. |
| **Authentik OIDC / SAML** | Inbound / Internal | HTTPS / JSON | OAuth2 Authorization Code Flow, PKCE | Centralized identity authentication and role-based token issuance. |
| **External LLM APIs** | Outbound | HTTPS (TLS 1.3) | Scoped API Keys, LiteLLM proxy | Optional connection to cloud inference backends (e.g. OpenAI, Anthropic). |
