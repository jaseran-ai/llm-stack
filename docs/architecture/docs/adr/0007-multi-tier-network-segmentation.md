# ADR 0007: Multi-Tier Network Segmentation

* **Status**: Accepted
* **Deciders**: LLM Stack maintainers
* **Date**: 2026-10-18
* **Technical Story**: Internal Docker network segmentation and database isolation

## Context and Problem Statement

Previously, all containers in the stack shared a single bridge network (`llm-stack_default`). Although Traefik and Cloudflared only route intended HTTP requests, any compromised web container (e.g., Open WebUI or Grafana) could attempt lateral network discovery or port scanning against internal databases (PostgreSQL, ClickHouse, Redis) on the Docker bridge. Furthermore, compromised database containers could potentially exfiltrate data outbound to the internet.

## Decision Drivers

* Defense-in-depth and strict network isolation between tiers.
* Isolation of relational, vector, and cache databases from internet-facing and web application containers.
* Zero external internet access for databases (`internal: true` bridge).
* Zero-downtime migration without breaking OIDC discovery or health check probes.
* Preservation of Traefik reverse-proxy routing and published services.

## Considered Options

1. **Single Bridge Network (Previous)**: Simple, zero routing complexity, but no lateral movement barrier.
2. **Strict Per-Service Network Isolation**: Too many networks, overhead, and complex mesh connectivity.
3. **Multi-Tier Network Segmentation**:
   - `llm-stack_default`: General application and edge routing bridge (`172.18.0.0/16`).
   - `internal-backend` (`name: llm-stack_backend`, `internal: true`, `172.24.0.0/16`): Isolated database and cache backend with no default gateway. Relational and cache databases (`postgres`, `clickhouse`, `redis`) reside exclusively on this network. Authorized application consumers (`authentik`, `litellm`, `langfuse-web`, `langfuse-worker`, `chouse-ui`, `betterleaks`, `gatus`) are dual-homed.

## Decision Outcome

Chosen option: **Multi-Tier Network Segmentation with Dedicated Internal Backend (`internal-backend`)**.

### Implementation Details

1. **Docker Compose Declarative Networks**:
   - `networks.default`: explicitly named `llm-stack_default`.
   - `networks.internal-backend`: explicitly named `llm-stack_backend` with `internal: true`.
2. **Database Isolation**:
   - `postgres`, `clickhouse`, and `redis` are attached exclusively to `internal-backend`.
   - Outbound internet access is blocked by the kernel (`Network is unreachable`).
   - Ingress from non-backend containers (e.g. `searxng`) is blocked at name resolution and IP routing levels.
3. **Traefik Reverse-Proxy Pinning**:
   - Configured `providers.docker.network: "llm-stack_default"` in `traefik/traefik.yml` and `traefik/traefik.yml.template` to prevent Traefik from inadvertently routing traffic to internal backend IP addresses of dual-homed containers.
4. **Empirical Validation**:
   - 28/28 smoke tests passing (`./smoke_test.sh`).
   - Internet egress block verified (`curl` / `wget` fails with `Network is unreachable`).
   - Lateral isolation verified (socket connections from untrusted containers fail name resolution).

### Positive Consequences

* Backend databases reside on a network with no default gateway (`internal: true`), completely preventing outbound data exfiltration even if code execution occurs.
* Lateral movement from compromised frontend containers to databases is strictly blocked by Docker.
* Traefik routing remains deterministic and protected against multi-IP ambiguities.
* Complies with high-assurance zero-trust benchmarks.

### Negative Consequences

* Dual-homed containers (e.g. Authentik, Langfuse, LiteLLM) must declare membership in both `default` and `internal-backend`.
* Database host port bindings are no longer published via `docker-proxy` to localhost (internal networks disable host port forwarding), requiring test suites and maintenance tools to execute within the Docker namespace (`docker compose exec`) or use internal container IPs.
