# Explanation: Zero-Trust Security & In-Memory Secrets

This document explains the zero-trust principles and memory-backed secret management model that protect the LLM Stack.

---

## Core Zero-Trust Tenets

The architecture operates on three zero-trust assumptions:
1. **The internal network is hostile**: Containers cannot assume unauthenticated access to neighboring services simply because they share a Docker bridge.
2. **Physical storage is persistent and insecure**: Plaintext secrets written to disk blocks can be recovered forensically or leaked via backups and accidental commits.
3. **Identity must be verified at every hop**: Session cookies and Bearer tokens must be validated continuously.

---

## The Zero-Disk Secret Architecture

```text
[setup.sh]
    │ (Generate random 256-bit keys)
    ▼
[HashiCorp Vault KV v2] (Encrypted master storage)
    │
    │ (AppRole Auth via HTTPS TLS listener)
    ▼
[Vault Agent Daemon]
    │ (Render Consul templates)
    ▼
[/vault/secrets_ram] ── (Isolated RAM-backed tmpfs mount, mode 0700)
    │
    ├─► open-webui.env (mode 0600)
    ├─► litellm.env (mode 0600)
    └─► langfuse.env (mode 0600)
```

### Why tmpfs?
* **Zero Persistence**: When the server reboots or shuts down, the RAM contents vanish immediately. No forensic tool can extract plaintext passwords from discarded hardware.
* **Granular Mounts**: Applications only mount the specific `.env` file required for their operation, preventing cross-container credential reading.
* **Strict Permissions**: The directory is locked to `0700` and files to `0600`, preventing access by unprivileged users.
