# Isolated DinD UAT Environment

This harness validates an exact Git commit in a Docker-in-Docker environment before a separately approved production deployment.

## Safety properties

- The UAT daemon never mounts the production Docker socket.
- UAT owns independent containers, networks, volumes, Vault data, and secrets.
- No UAT application port is published on the VM.
- The smoke-test runner shares the DinD network namespace, where the existing localhost endpoints reach UAT.
- Application hostnames resolve through the DinD container's inherited hosts file.
- Cloudflare is disabled for UAT.
- Production deployment is never automatic.
- The committed `litellm/custom_models.yaml` is restored in the worktree so
  private host overrides cannot leak into UAT through Git's shared index.
- Docker images and build layers live in a persistent DinD cache volume.
- Ollama model weights live in a separate persistent cache volume.
- Each disposable run gets a private `tmpfs` Docker volume for Vault-rendered files and scoped AppRole credentials. The volume is mounted at the same `/dev/shm/llm-stack-vault-secrets-<id>` path in the DinD controller and smoke runner; the worktree contains only a symlink, not rendered secret files.
- Application containers and volumes are erased when a run is destroyed, so
  Vault, database, and application state always start from a clean state.

## Configuration

Copy `uat/uat.env.example` to `uat/.env` and set every value explicitly. `UAT_CANDIDATE_SHA` identifies the exact commit to validate. `UAT_WORKTREE` must point to `uat/runtime/worktree` using its absolute path.

Every `make uat-setup` creates a new disposable run identifier and worktree. The generated metadata lives in ignored `uat/runtime/run.env`; it binds the candidate SHA and worktree together. A prepared run is never reused for another candidate. `UAT_DOCKER_CACHE_VOLUME` stores reusable Docker images and build layers. `UAT_OLLAMA_MODEL_VOLUME` stores only the contents mounted at `/root/.ollama/models`. Both cache volumes persist across runs.

The UAT run also generates a separate 16-character RAM instance ID before setup.
`setup.sh` records the ID in the disposable worktree `.env` and creates a symlink;
`start.sh` verifies that link, the `tmpfs` filesystem, owner, and mode before Vault
starts. This exercises the same host-path lifecycle planned for a fresh Linux clone.

The UAT setup records the operator's numeric user and group IDs. Vault Agent runs with
the operator UID and the pinned SeaweedFS image's process GID (`1000`). It writes mode
`0600` files; the account and S3 files alone are mode `0640` so their designated
consumers can read them through file-specific mounts. The
production runtime and its current secret directory are not changed by an UAT run.

For the legacy-directory migration rehearsal on a newly prepared UAT, run
`scripts/uat/rehearse-vault-legacy.sh` between `make uat-setup` and
`make uat-start`. It requires an empty inner Docker daemon, creates only
synthetic legacy credentials, invokes the same CAB-gated migration tool, and
verifies that the new RAM directory is empty before first boot. See
[`vault/MIGRATION.md`](../vault/MIGRATION.md). This is not a production cutover.

## Phase B commands

These commands are documented but must not be run without the separate runtime approval required by the CAB:

```bash
make uat-preflight
make uat-setup
make uat-start
make uat-smoke-test
make uat-status
make uat-stop
make uat-destroy
```

A successful UAT result authorizes neither a production deployment nor a LiteLLM restart. Production promotion always requires its own CAB and explicit approval. `make uat-destroy` irreversibly removes all application containers, volumes, generated TLS material, secrets, and data for the current UAT run while preserving the DinD image cache and Ollama model cache; it requires explicit CAB approval.

## Access through an SSH tunnel

UAT uses `llm-stack.test` and its service subdomains without public DNS or Cloudflare. Retrieve the DinD container address on the VM:

```bash
docker inspect llm-stack-uat-docker \
  --format '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'
```

Map the required `llm-stack.test` hostnames to `127.0.0.1` on the client machine, then forward the privileged HTTP and HTTPS ports to that container address:

```bash
sudo ssh \
  -L 80:DIND_CONTAINER_ADDRESS:80 \
  -L 443:DIND_CONTAINER_ADDRESS:443 \
  user@vm-address
```

Keeping ports 80 and 443 preserves the exact Authentik and OIDC callback URLs. The internal UAT certificate authority may need to be trusted on the client machine. Remove the local hostname mappings after testing.

## Version provenance

- Docker DinD 29.7.2 was verified against the Docker Official Image catalog.
- Python 3.14.7 on Alpine 3.24 was verified against the Python Official Image catalog.

Provisioning and smoke-test HTTP calls use only the Python standard library through
`scripts/http_client.py`. The DinD controller and smoke-test image contain no third-party Python
HTTP package, and no package is downloaded at runtime.

The S3 smoke check uses Vault Agent's RAM-rendered SeaweedFS credentials and verifies
the internal wildcard certificate. It signs a unique PUT, GET, and cleanup DELETE;
no credential is placed in a command line or log.

All public configuration remains in English. Runtime files under `uat/runtime/` and `uat/.env` are local and must never be committed.
