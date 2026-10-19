# 7. Deployment View

This section describes the physical and containerized deployment infrastructure of the LLM Stack.

---

## 7.1 Infrastructure & Host Environment

The platform runs on a single Linux host (Debian, Ubuntu, or RHEL-compatible distribution) with Docker Engine and Docker Compose:

* **Operating System**: Linux 6.x kernel with cgroups v2 enabled.
* **Storage Architecture**:
  * **Persistent Volumes**: Named Docker volumes (`postgres_data`, `clickhouse_data`, `seaweedfs_data`, `qdrant_data`, `vault_data`, `loki_data`) mapped to the host filesystem.
  * **Volatile Memory Volume (`tmpfs`)**: An isolated 64MB RAM-backed tmpfs (`secrets_ram`) mounted on `/vault/secrets_ram` with permissions `0700` for the directory and `0600` for files.
* **Perimeter Ingress**: No inbound router ports are required. All traffic is tunneled through `cloudflared` to Cloudflare Zero Trust.

---

## 7.2 Container Topology

```text
Host (Single Node Linux Server)
│
├── Cloudflare Zero Trust Edge (DNS, WAF, min TLS 1.2)
│   └── [Outbound QUIC / HTTPS Tunnel]
│
├── Ingress Tier
│   ├── cloudflared
│   └── traefik (Reverse Proxy, :80, :443, :8080 admin, :8082 metrics)
│
├── Security & Identity
│   ├── authentik-server & authentik-worker
│   ├── vault (Internal TLS :8200) & vault-agent (tmpfs renderer)
│   └── betterleaks-presidio (:8080 HTTP, :50052 gRPC)
│
├── Applications & Gateways
│   ├── open-webui (:8080)
│   ├── litellm (:4000)
│   ├── searxng (:8080) & chouse-ui (:5521)
│   └── ollama (:11434 CPU inference)
│
├── Persistence & Caching
│   ├── postgres (:5432)
│   ├── clickhouse-server (:8123, :9000)
│   ├── seaweedfs (:8888 Filer, :8333 S3)
│   ├── qdrant (:6333)
│   └── redis (:6379)
│
└── Observability
    ├── prometheus (:9090) & alertmanager (:9093)
    ├── grafana (:3000)
    ├── vector (socket listener) & loki (:3100)
    ├── dozzle (:8080) & gatus (:80)
    └── cadvisor & node-exporter
```

---

## 7.3 Network Topology & Multi-Tier Segmentation

The stack uses a segmented multi-network architecture to enforce defense-in-depth and prevent lateral movement or data exfiltration:

| Network Name | Docker Driver | Internal / Air-Gapped | Subnet Range | Assigned Services | Purpose |
|---|---|---|---|---|---|
| `llm-stack_default` | bridge | No (Outbound Gateway) | `172.18.0.0/16` | Traefik, Cloudflared, Open-WebUI, Ollama, Qdrant, SeaweedFS, Observability agents, dual-homed applications | Edge routing, user traffic, and external provider connectivity. Traefik Docker provider is pinned to this network. |
| `llm-stack_backend` | bridge | **Yes (`internal: true`)** | `172.24.0.0/16` | `postgres`, `clickhouse`, `redis` (exclusively), plus dual-homed consumers (`authentik`, `litellm`, `langfuse`, `chouse-ui`, `betterleaks`, `gatus`) | Air-gapped database backend with zero default gateway. Prevents outbound data exfiltration and blocks lateral access from untrusted layers. |

---

## 7.4 Multi-Arch Portability & Digests

To enforce absolute reproducibility across developer laptops (e.g. Apple Silicon `linux/arm64`) and production servers (`linux/amd64`):
* Every service in `docker-compose.yml` specifies a multi-arch multi-platform manifest digest (`@sha256:...`).
* Builds of local custom images (`betterleaks-presidio`) leverage multi-stage Dockerfiles supporting native compilation on both architectures.

