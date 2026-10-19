# ADR 0002: Vault KV v2 and tmpfs Memory Secrets

* **Status**: Accepted
* **Deciders**: LLM Stack maintainers
* **Date**: 2026-08-20
* **Technical Story**: Security hardening of secret storage and zero-disk persistence

## Context and Problem Statement

Initially, secrets were generated into a root `.env` file or rendered by Vault Agent into a host directory on physical disk. This posed critical security risks: plaintext secrets persisted in block storage, vulnerability to forensic disk recovery, risks of accidental git commits, and exposure across container boundaries.

## Decision Drivers

* Zero plaintext secrets committed to version control.
* Zero plaintext secrets written to physical non-volatile storage.
* Dynamic secret lifecycle management via HashiCorp Vault KV v2.
* Automated runtime rendering without human intervention or manual unsealing.

## Considered Options

1. **Static `.env` on Host Disk**: Simplest, but high risk of secret leakage, unencrypted disk forensics, and no audit trail.
2. **OpenBao External Deployment**: Evaluated for multi-operator teams, but introduces Shamir seal operational complexity on single-host deployments.
3. **Vault KV v2 + Vault Agent tmpfs Rendering**: Dynamic secret provisioning via python scripts into Vault KV v2, with Vault Agent rendering into an isolated RAM-backed `tmpfs` volume with strict `0700`/`0600` permissions.

## Decision Outcome

Chosen option: **Vault KV v2 + tmpfs Memory Secrets**, because it guarantees that sensitive credentials reside exclusively in volatile RAM and are wiped upon reboot.

### Positive Consequences

* Secrets are never flushed to disk blocks, mitigating offline forensic recovery.
* File permissions are strictly constrained (`0700` directory, `0600` files).
* Vault Agent continuously refreshes templates and handles AppRole re-authentication automatically.
* Zero fallback defaults allowed in `docker-compose.yml` (`${VAR}` bare syntax enforced).

### Negative Consequences

* On cold boot, secrets must be rendered by Vault Agent before downstream containers can read their environment files (managed by container dependency health checks).
