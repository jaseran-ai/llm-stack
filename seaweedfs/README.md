# SeaweedFS Architecture & Operational Reference

SeaweedFS provides S3-compatible object storage and distributed file storage across the stack.

---

## 🏛️ Architecture & Integration

- **Container Port**: Exposed on `127.0.0.1:8333` (S3 API) and `127.0.0.1:8888` (Filer UI Console).
- **Reverse Proxy & Routing**:
  - `https://s3.${DOMAIN}` routes directly to the S3 API endpoint (:8333).
  - `https://s3-console.${DOMAIN}` routes to the web-based Filer interface (:8888), gated by Authentik Forward-Auth for administrators.
- **Consumers**:
  - **Langfuse**: stores trace events, media uploads, and batch exports in dedicated S3 buckets.
  - **Backups**: supports off-site state replication and recovery artifacts.

---

## 🔑 Credentials & S3 Identity Management (`s3.json`)

SeaweedFS reads its S3 user accounts and permissions from a configuration file:
- Mounted at `/run/secrets/s3.json:ro` rendered dynamically by Vault Agent into private tmpfs.
- Declares identities and policy actions (`Read`, `Write`, `List`, `Tagging`, `Admin`):
  - `seaweed_admin`: administrative account for maintenance and diagnostics.
  - Automated service identities for Langfuse and background jobs.

---

## ⚙️ Operational Considerations & Memory Headroom

- SeaweedFS runs in unified mode (`server -s3 -dir=/data`), managing volume allocation, indexing, and S3 translations in a single process.
- **Resource Limits**: Configured in `docker-compose.yml` with memory limits to prevent uncontrolled cache expansion on memory-constrained systems (such as ARM64 single-board computers).
- **Volume Persistence**: Data volumes (`seaweedfs_data`) are mounted under `/data` and backed up via `scripts/backup.sh`.
