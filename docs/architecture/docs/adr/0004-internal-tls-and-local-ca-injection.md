# ADR 0004: Internal TLS and Local CA Injection

* **Status**: Accepted
* **Deciders**: LLM Stack maintainers
* **Date**: 2026-10-18
* **Technical Story**: Internal TLS listener hardening and elimination of global verification bypass flags

## Context and Problem Statement

To enable internal HTTPS communication between containers without public certificate authority chains, earlier iterations resorted to global TLS verification bypass flags (`NODE_TLS_REJECT_UNAUTHORIZED="0"`, `PYTHONHTTPSVERIFY="0"`, `SSL_VERIFY="false"`). This disabled cryptographic validation entirely, making the services vulnerable to machine-in-the-middle attacks on outbound internet requests (e.g., LiteLLM pulling model cost maps or Langfuse calling external APIs).

## Decision Drivers

* Elimination of all insecure global TLS bypass flags.
* Encryption of internal communication channels (e.g., Vault listener).
* Full certificate verification for internal OIDC discovery endpoints (`https://authentik.${DOMAIN}/...`).
* Strict preservation of standard Mozilla root CA verification for external internet traffic.

## Considered Options

1. **Global Bypass Flags**: Simple, but critical security flaw leaving all external HTTPS connections unverified.
2. **Replacing System Trust Store via `SSL_CERT_FILE` in Python**: Breaks external public HTTPS calls in Python because `SSL_CERT_FILE` completely overrides system roots.
3. **Targeted Node.js `NODE_EXTRA_CA_CERTS` + Python Selective Trust**: Mounting the local CA certificate (`traefik/certs/tls.crt`) into `/etc/ssl/certs/local-ca.crt` and injecting it specifically into Node.js via `NODE_EXTRA_CA_CERTS` (which appends without overriding), while keeping Python's default public trust store intact.

## Decision Outcome

Chosen option: **Targeted Local CA Injection**, enabling internal TLS on Vault (`tls_disable = 0`) with Traefik `serversTransport` rootCA verification, and injecting the local CA into Node.js containers without compromising external Python HTTPS validation.

### Positive Consequences

* Global bypass flags (`NODE_TLS_REJECT_UNAUTHORIZED="0"`, `PYTHONHTTPSVERIFY="0"`) are completely eliminated.
* Internal OIDC discovery succeeds over TLS with valid certificate verification.
* Outbound internet requests continue to be verified against official public root certificates.
* Vault internal traffic is 100% encrypted and mutually verified by Traefik.

### Negative Consequences

* Requires mounting the local CA certificate as a read-only volume into Node.js containers.
