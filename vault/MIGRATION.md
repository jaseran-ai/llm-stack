# Legacy render-directory migration (CAB-gated)

The fresh-install design renders Vault Agent files in a private per-instance
`/dev/shm` directory. Existing installations may instead have a nonempty
`vault/secrets_ram` directory on persistent storage. `setup.sh` intentionally
refuses to replace that directory. Never bypass this refusal by deleting its
contents or changing it to a symlink by hand.

## What the migration tool does

`python3 vault/scripts/migrate_secrets.py` is a read-only preflight. It checks
that the legacy path is a regular directory, that its entries are regular
files, that `.env` is owner-only, and that no running Docker container has a
direct bind mount of the directory or a contained file. Docker inspection
errors are fatal. It does not reveal secret values.

`python3 vault/scripts/migrate_secrets.py --execute` additionally adds only
missing `SECRETS_RAM_*` metadata to `.env` without regenerating application
secrets. It narrows the legacy directory to mode `0700`, atomically moves the
entire directory to `vault/.secrets_ram.legacy-<id>`, creates the expected
repository symlink, and verifies an empty private tmpfs target. The quarantine
is gitignored but persists on disk; it is **not** a credential rotation or a
complete removal of old secrets from persistent storage. The tool never copies
the legacy Agent token into RAM. An error during the filesystem transition
restores the legacy path privately and leaves services stopped for inspection.

The direct-mount check is a last line of defense, not a scheduler or a lock:
the operator must keep the affected services stopped throughout the cutover.
Do not start an old container or run `start.sh` between the check and the
service recreation. No production execution is authorized by this document.

## Disposable UAT rehearsal

Use the candidate commit with the standard UAT setup. Before its first start,
run `scripts/uat/rehearse-vault-legacy.sh`. The rehearsal verifies the UAT
identity and empty inner Docker daemon, replaces only the prepared unused UAT
symlink with synthetic legacy files, runs the real migration tool, and checks
that the synthetic credential remains only in the private quarantine. Then
run `make uat-start` and `make uat-smoke-test`; require a clean first start and
all smoke tests. This exercises the migration path and the normal startup
without touching production data or its Docker daemon.

## Production hold points (separate CAB required)

1. Record production container health and Vault status. Securely preserve the
   required state in a private working directory; never copy credentials into
   an ordinary report or terminal log. Confirm the exact stopped-service list
   and a maintenance window. The current single LiteLLM instance cannot be
   recreated without a brief interruption; its production restart requires
   explicit approval.
2. Stop Vault Agent and every container with a direct legacy bind mount,
   including LiteLLM, before running the migration. Keep unrelated databases
   and persistent volumes intact. Do not edit the live mounted Agent config
   while its process is running.
3. Run the preflight, then `--execute`, and verify the symlink, tmpfs filesystem,
   owner/mode, and private quarantine. Provision the scoped AppRole and start
   Vault Agent before recreating only the affected application containers.
   The exact sequence and commands must be CAB-approved against live state.
4. Immediately inspect new container mounts, Vault Agent logs, health checks,
   and the full production smoke test. Stop at the first failure. Do not
   roll back by remounting a broadly readable root token. Preserve the
   quarantine until the credential-rotation and retention decision is approved.

The bootstrap scripts still use `.vault_keys.json`. Revoking the old root
token before replacing that dependency would break automated unseal and
provisioning. Conversely, the migration alone does not neutralize a previously
exposed, still-valid root token. Root-token redesign and revocation are a
required separate security hold point before declaring the secret-storage hardening complete.
