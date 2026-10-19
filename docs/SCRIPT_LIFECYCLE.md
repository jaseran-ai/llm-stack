# Script Lifecycle and Ownership

This document records the supported script entry points, their ownership boundaries, and the
remaining migrations identified by the August 2026 script audit.

## Canonical lifecycle

| Responsibility | Supported entry point | Owner |
| --- | --- | --- |
| Generate `.env` and render configuration | `./setup.sh` | Configuration phase |
| Start services through readiness gates | `./start.sh` | Runtime phase |
| Stop containers while preserving volumes | `./stop.sh` | Runtime phase |
| Restart the stack | `./restart.sh` | Runtime phase |
| Run functional acceptance tests | `./smoke_test.sh` | Validation phase |
| Manage isolated acceptance environments | `./scripts/uat/*.sh` | UAT harness |

`setup.sh` does not start containers. `start.sh` owns runtime ordering: Vault, Vault Agent,
Prometheus hydration, the Authentik reconciliation gate, dependent services, and application
provisioners. The declarative dependency contract is documented in
[startup-dependency-graph.md](startup-dependency-graph.md).

## Provisioning scripts

Service-level `provision.sh` and `scripts/provision.py` files are active implementation details
called by `start.sh`; they are not independent stack entry points. Authentik reconciliation is
the exception: Compose runs `authentik/provision.sh` inside the one-shot
`authentik-provision` service.

## Automated validation

`make script-tests` is the canonical unit-test entry point. It covers:

- the shared standard-library HTTP client (cookies, redirects, JSON, forms, basic auth,
  multipart uploads, and HTTP error responses);
- Authentik blueprint hydration, sequential reconciliation, outpost binding, and passwords;
- the static Compose startup dependency graph contract;
- Vault initialization and OIDC sequencing;
- Prometheus secret-backed configuration hydration.

`make lint` includes `make script-tests`, and CI executes the same target in a pinned Python
container.

## Backup and restore ownership

`scripts/backup.sh` and `scripts/restore.sh` own the canonical versioned encrypted format. The
root `backup.sh` and `restore.sh` files are compatibility entry points, while the Makefile exposes
the supported operator interface. Backup validation and destructive-operation guards are covered
by `make backup-restore-tests`.

Online backups are explicitly classified as best-effort. Only an offline backup followed by a
successful isolated restore exercise and full smoke suite is disaster-recovery evidence. See
[BACKUP_AND_RESTORE.md](BACKUP_AND_RESTORE.md).

## HTTP client reproducibility

Vault, Langfuse, LiteLLM, Open WebUI provisioning, and the smoke suite import the shared
`scripts/http_client.py` module. It uses only the Python standard library and implements the
bounded feature set required by this repository: persistent cookies, configurable redirects and
TLS verification, timeouts, JSON, forms, basic authentication, and multipart uploads. Neither
host package installation nor runtime package downloads are part of the supported lifecycle.

## Admin credential migration

The initial stack bootstrap used one static development password for the admin account. The
LiteLLM and Langfuse OIDC seeding flows copied that literal when they were introduced on August
9, 2026. Commit `94aa614` changed `setup.sh` to generate a unique `UI_PASSWORD` on August 22,
but did not update those two seeding flows or all public credential examples. Commit `15087c3`
then made Authentik password synchronization and the functional tests consume the generated
value, leaving the seeding scripts behind.

This split was exposed by the disposable Phase 3 UAT on August 29: both startup seeding logins
used the obsolete credential and remained on the Authentik login flow. The later smoke suite
used the generated credential and passed both application OIDC tests, while Langfuse's
idempotent SQL membership reconciliation also allowed startup to continue. The final UAT result
was 22/22, but the startup messages prove that the lifecycle still contains a hidden fallback
path and misleading successful reconciliation output.

The migration removed every static admin credential and fallback from the LiteLLM and Langfuse
provisioners, the smoke suite, and public documentation. `UI_PASSWORD` is now required from the
exported setup environment. Missing values, failed OIDC landings, SQL errors, and incomplete
Langfuse membership reconciliation fail startup closed. Focused unit tests prove that the
configured value reaches both OIDC login calls and that missing values stop execution. No
generated or historical credential value belongs in this document.

## Removed historical automation

The one-time GitHub release bootstrap script for releases `v0.1.0` through `v0.5.0` was removed
after the releases had been published. Future releases require a separately reviewed release
procedure, not a replay of historical `gh release create` commands.
