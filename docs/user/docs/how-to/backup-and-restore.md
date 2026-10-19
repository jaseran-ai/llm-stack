# How-To: Execute Encrypted Backups & Scoped Disaster Recovery

This guide explains how to perform atomic backups of all stack databases and execute point-in-time disaster recoveries.

---

## 1. Creating an Encrypted Backup

The automated backup script dumps relational databases, creates vector snapshots, archives volumes, and encrypts everything using GnuPG AES-256:

```bash
./backup.sh
```

### What is backed up:
* **PostgreSQL databases**: Full SQL dump via `pg_dumpall` (covering Authentik, LiteLLM, Langfuse, CHouse UI).
* **Qdrant Vector DB**: Point-in-time collection snapshots.
* **Storage Volumes**: SeaweedFS S3 metadata and Vault state (`vault_data`).
* **Vault Unseal Material**: Encrypted copy of `.vault_keys.json`.

The output is written to `backups/backup_YYYYMMDD_HHMMSS.tar.gz.gpg` with permissions `0700`.

---

## 2. Restoring from a Backup

To restore the stack to a known healthy state:

1. Locate the desired backup archive in `backups/`.
2. Execute the restore script, providing the path and SHA256 checksum:
   ```bash
   ./restore.sh --archive backups/backup_20261018_100000.tar.gz.gpg
   ```
3. Enter the `BACKUP_PASSPHRASE` generated during `./setup.sh`.
4. The restore script automatically:
   * Validates archive checksum and integrity before touching running services.
   * Gracefully pauses writing containers (`litellm`, `langfuse-worker`, `authentik-worker`).
   * Restores PostgreSQL schemas, Qdrant snapshots, and SeaweedFS filer metadata.
   * Verifies database consistency and restarts application services.
   * Runs `./smoke_test.sh` to confirm full recovery.

---

## 3. Scoped Rollbacks for Langfuse

For scenarios where only LLMOps traces need point-in-time restoration without reverting user authentication:
```bash
python3 scripts/langfuse_snapshot.py rollback --archive backups/langfuse_snapshot_latest.tar.gz.gpg
```
This performs a safe, scoped restoration of Langfuse data while leaving the global platform operational.
