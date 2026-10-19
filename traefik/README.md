# Traefik v3 — Cloud-Native Reverse Proxy, Routing & Dynamic Ingress

A modern, declarative, edge reverse proxy integrated into `llm-stack`. Handles virtual subdomains, dynamic Docker provider route discovery, forward-authentication via Authentik, and SSL/TLS termination across multiple deployment scenarios.

---

## 🏗️ Architecture & Component Integration

| Component | Role | Configuration / Path |
| :--- | :--- | :--- |
| **`traefik`** | Core reverse proxy (`traefik:v3.6.1`). Listens on ports `80` (HTTP) and `443` (HTTPS). | [`traefik.yml`](traefik.yml), [`dynamic.yml`](dynamic.yml), [`docker-compose.yml`](../docker-compose.yml). |
| **Hydration Script** | Generates static and dynamic configs based on `TLS_MODE` and `DOMAIN`. | [`scripts/hydrate_traefik.py`](scripts/hydrate_traefik.py). |
| **Docker Provider** | Dynamic route discovery via container labels (`traefik.http.routers.*`). | Declared on each service in [`docker-compose.yml`](../docker-compose.yml). |
| **Authentik Forward-Auth** | Middleware protecting interactive and administrative endpoints. | Middleware `authentik-auth@file` pointing to `http://authentik-server:9000/outpost.goauthentik.io/auth/traefik`. |

---

## 🔑 Key Features & Subtleties

### 1. Dual Entrypoint Routing (Cloudflare Tunnel + Direct HTTPS)
* Traefik exposes two distinct entrypoints:
  * **`web` (`:80`)**: Accepts internal plaintext HTTP traffic forwarded by Cloudflare Tunnel (`cloudflared`) with `X-Forwarded-*` trusted headers.
  * **`websecure` (`:443`)**: Handles direct TLS connections with automated certificate management.
* Each container specifies dual routers (e.g. `chat` on `websecure` and `chat-http` on `web`) to ensure seamless traffic flow without endless redirect loops.

### 2. TLS Termination Modes (`TLS_MODE`)
Controlled via `.env`:
* **`internal` (Default)**: Automatically generated self-signed local certificates for private testing and internal networks.
* **`http-01`**: Automatic Let's Encrypt certificates via ACME HTTP-01 challenge for standard publicly accessible servers.
* **`cloudflare-dns01`**: Automated DNS-01 challenge using Cloudflare API tokens for environments without inbound open ports.
