# Tutorial: Add a New Application to the Stack

This tutorial guides you through adding a new containerized service to the LLM Stack following the standard 7-step integration workflow.

---

## Step 1: Version Audit & Registry Pinning
Identify the exact, latest stable container release tag or SHA256 digest from the upstream registry (e.g., Docker Hub or GitHub Container Registry). Never use `:latest`.

---

## Step 2: Architecture & Authentication Model
Determine whether the application supports **Pattern A** (Forward-Auth) or **Pattern B** (Native OIDC):
* Use **Pattern A** if the service has no built-in OIDC support. Traefik will enforce authentication before routing.
* Use **Pattern B** if the service can natively federate with an OpenID Connect provider.

---

## Step 3: Service Declaration in Docker Compose
Add the container definition to `docker-compose.yml`:
```yaml
  my-app:
    image: vendor/my-app:1.2.3@sha256:abcdef...
    container_name: my-app
    restart: unless-stopped
    networks:
      - llm-stack-network
    environment:
      MY_APP_SECRET: ${MY_APP_SECRET}
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.my-app.rule=Host(`my-app.${DOMAIN}`)"
      - "traefik.http.routers.my-app.entrypoints=websecure"
      - "traefik.http.routers.my-app.tls=true"
      - "traefik.http.routers.my-app.middlewares=security-headers@file,authentik-auth@file"
```

---

## Step 4: Secret Provisioning in Vault
1. Add the secret placeholder to `.env.example`.
2. Update `vault/scripts/provision.py` to seed `MY_APP_SECRET` into Vault KV v2.
3. Update `vault/agent-config.hcl` and `vault/templates/my-app.env.tpl` so Vault Agent renders the secret to the in-memory tmpfs mount.

---

## Step 5: Authentik SSO Integration
Create a declarative YAML blueprint in `authentik/blueprints/`:
* Define the Provider (Proxy Provider for Pattern A, OAuth2 Provider for Pattern B).
* Define the Application with a verified CDN tile icon (`https://cdn.jsdelivr.net/gh/selfhst/icons/png/<name>.png`).
* Attach access policies restricting the application to the `admins` or `users` group.

---

## Step 6: GitOps Health Monitoring in Gatus
Add a health probe entry in `gatus/config.yaml.template`:
```yaml
  - name: my-app
    group: applications
    url: "https://my-app.${DOMAIN}/healthz"
    interval: 60s
    conditions:
      - "[STATUS] == 200"
```

---

## Step 7: Empirical Validation
1. Run `./setup.sh` to apply configurations and launch the container.
2. Add an automated test in `scripts/smoke_test.py` asserting that the application responds with HTTP 200 and enforces RBAC.
3. Validate everything:
   ```bash
   ./smoke_test.sh
   make lint
   ```
