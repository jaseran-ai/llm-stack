# Backup and Disaster Recovery

> [!IMPORTANT]
> **This operational guide has been migrated to the User Documentation (Diátaxis How-To section).**
> Please refer to:
> - **English**: [`docs/user/docs/how-to/backup-and-restore.md`](user/docs/how-to/backup-and-restore.md)
> - **French**: [`docs/user/i18n/fr/docusaurus-plugin-content-docs/current/how-to/backup-and-restore.md`](user/i18n/fr/docusaurus-plugin-content-docs/current/how-to/backup-and-restore.md)

---

## Backup modes

```bash
# No service interruption. Raw-volume captures are explicitly best-effort.
make backup

# Briefly stop raw-volume writers. This is the DR-qualified mode.
make backup CONSISTENCY=offline
```

Both modes use logical PostgreSQL dumps and native Qdrant collection snapshots. The difference
applies to filesystem volumes for Open WebUI, Vault, ClickHouse, SeaweedFS, Grafana, and Authentik
media.

- `online` is suitable for frequent operational checkpoints. Its manifest records
  `CONSISTENCY=online`, and restore refuses it unless the operator explicitly accepts the risk.
- `offline` stops the relevant writers before archiving their volumes and records
  `CONSISTENCY=offline`. Vault uses its filesystem storage backend, for which an offline copy is
  required because that backend has no atomic snapshot API.

Offline backup does not stop PostgreSQL, Qdrant, or LiteLLM. It briefly stops Open WebUI,
Langfuse, CHouse UI, ClickHouse, SeaweedFS, Grafana, Authentik, Vault Agent, and Vault. The script
restarts anything it stopped, including on failure, and unseals Vault before returning.

## Canonical format

Each run produces two owner-readable files:

```text
backups/llm_stack_backup_YYYYMMDD_HHMMSS.tar.gz.enc
backups/llm_stack_backup_YYYYMMDD_HHMMSS.tar.gz.enc.sha256
```

The archive is encrypted with AES-256-CBC and PBKDF2-HMAC-SHA256 using 200,000 iterations and a
random salt. The SHA-256 sidecar detects corruption; it is not a digital signature and does not
establish provenance. Cleartext payloads exist only in an owner-only temporary directory and are
removed by the exit trap. They are not claimed to be memory-backed.

The decrypted version 2 payload contains:

```text
manifest.env
files.sha256
postgres/cluster.sql
qdrant/collections.tsv
qdrant/<collection>.snapshot
configs/env
configs/vault_keys.json
configs/custom_models.yaml
configs/targets.d/
volumes/open-webui.tar.gz
volumes/vault_data.tar.gz
volumes/clickhouse_data.tar.gz
volumes/clickhouse_logs.tar.gz
volumes/seaweedfs_data.tar.gz
volumes/grafana_data.tar.gz
volumes/authentik_media.tar.gz
```

The restore preflight validates the external checksum, decryptability, archive paths, format
version, consistency classification, internal checksums, and the complete mandatory inventory
before it asks for confirmation or changes runtime state.

## Restore

List canonical archives:

```bash
make backups
```

Restore one component that does not depend on PostgreSQL:

```bash
make restore BACKUP=20260829_030001 COMPONENT=qdrant
```

A full restore and a PostgreSQL restore interrupt LiteLLM and therefore require both CAB approval
and the explicit runtime guard:

```bash
make restore BACKUP=20260829_030001 ALLOW_LITELLM_RESTART=yes
```

The script then requires the exact encrypted archive basename to be typed. Automation may pass
the same value through `CONFIRM_RESTORE`, but doing so does not replace CAB approval.

Online backups are rejected by default. An exceptional restore requires explicit risk acceptance:

```bash
ALLOW_BEST_EFFORT_RESTORE=yes \
  make restore BACKUP=20260829_030001 COMPONENT=open-webui
```

Supported components are `postgres`, `qdrant`, `open-webui`, `vault`, `clickhouse`, `seaweedfs`,
`grafana`, `authentik-media`, and `configs`. After a full restore, the canonical startup
orchestrator reconciles Vault, Authentik, and application provisioning. Recovery is not complete
until `./smoke_test.sh` passes.

### Database-scoped metadata rollbacks

For targeted rollbacks of Langfuse PostgreSQL metadata without interrupting LiteLLM, Authentik, or the rest of the cluster, use `scripts/langfuse_snapshot.py rollback` (see [`langfuse/README.md`](../langfuse/README.md) for details).

## Scheduling and retention

The existing host cron job calls `./scripts/backup.sh` without a consistency argument, so it
continues to create online, best-effort checkpoints without introducing a new production outage.
Changing that job to `--consistency offline` changes runtime availability and requires a separate
CAB.

`BACKUP_KEEP_DAYS` defaults to seven days. Set it to `0` to disable automatic pruning. Retention
only targets canonical encrypted archives and their checksum sidecars.

## Recovery guarantees and limitations

- PostgreSQL uses [`pg_dumpall --clean --if-exists`](https://www.postgresql.org/docs/current/app-pg-dumpall.html).
  PostgreSQL documents that some harmless
  restore errors may occur for built-in roles and databases; the script additionally verifies
  the required application databases after replay.
- [Qdrant snapshots](https://qdrant.tech/documentation/snapshots/) are restored with
  `priority=snapshot`, as required when the snapshot should
  take precedence over existing collection state.
- HashiCorp recommends an offline backup for a backend without atomic snapshots; this stack uses
  Vault's [filesystem storage backend](https://developer.hashicorp.com/vault/docs/configuration/storage/filesystem).
- Raw filesystem archives are DR-qualified only when their manifest says `offline`.
- Prometheus, Loki, Ollama models, Gatus history, Alertmanager state, and Traefik certificates are
  excluded because they are operational history, caches, or regenerable state rather than core
  application data.
- The encrypted archive contains `.env`, Vault unseal material, and private extensions. Protect
  the passphrase separately and keep archive permissions restricted.
- A local archive is not a 3-2-1 strategy. Off-site replication and periodic isolated restore
  exercises remain operational responsibilities.

## Isolated restore exercise

Every material change to this subsystem must be tested in disposable UAT:

1. create an offline encrypted backup inside UAT;
2. run the destructive full restore only against UAT volumes;
3. allow the UAT LiteLLM interruption explicitly;
4. reconcile the UAT stack;
5. require the complete smoke suite to pass;
6. prove the production runner and production LiteLLM identities did not change.

Creating an archive alone is never accepted as recovery evidence.
