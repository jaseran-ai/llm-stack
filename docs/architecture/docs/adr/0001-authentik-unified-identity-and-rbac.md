# ADR 0001: Authentik Unified Identity and RBAC

* **Status**: Accepted
* **Deciders**: LLM Stack maintainers
* **Date**: 2026-08-15
* **Technical Story**: Migration from Authelia and Homarr to unified IdP with declarative blueprints

## Context and Problem Statement

The platform previously maintained fragmented identity solutions: Authelia for reverse-proxy authentication, Homarr for the dashboard portal, and manual accounts for services. This created configuration duplication, lack of native OIDC provider support, and synchronization drift between dashboard visibility and actual access rights.

## Decision Drivers

* Single Source of Truth for identity, groups, and authentication across all services.
* Support for both reverse-proxy Forward-Auth (Pattern A) and native OpenID Connect (Pattern B).
* 100% declarative provisioning through versioned blueprints (no manual GUI setup).
* Multi-tenant role-based access control with distinct `admins` and `users` privileges.

## Considered Options

1. **Authelia + Homarr**: Lightweight, but lacking native OIDC provider support and declarative per-app dashboard permissions.
2. **Keycloak**: Feature-complete, but heavy Java/JVM memory footprint incompatible with lightweight single-machine operation.
3. **Authentik**: Python/Go modular IdP with native OIDC, Forward-Auth outpost, built-in application portal, and declarative YAML blueprints.

## Decision Outcome

Chosen option: **Authentik**, because it natively consolidates identity management, Forward-Auth, OIDC provider capabilities, and the application launcher dashboard into a single declarative engine.

### Positive Consequences

* Single IdP eliminates user and password synchronization across multiple authentication engines.
* Native OIDC enables secure OAuth2 code flows for LiteLLM, Langfuse, CHouse UI, and HashiCorp Vault.
* Forward-Auth outpost protects non-OIDC web interfaces (Grafana, Dozzle, Qdrant, SearXNG, SeaweedFS Console).
* Native application dashboard replaces Homarr, reducing resource consumption by one entire container.

### Negative Consequences

* Higher memory footprint than Authelia (requires Redis worker queue and PostgreSQL database).
* Requires careful blueprint sequencing to prevent Celery transaction deadlocks (resolved by 3-tier blueprint hierarchy).
