# Guide: Adding a New Application to `llm-stack`

> [!IMPORTANT]
> **This tutorial has been migrated to the User Documentation (Diátaxis Tutorials section).**
> Please refer to:
> - **English**: [`docs/user/docs/tutorials/add-an-application.md`](docs/user/docs/tutorials/add-an-application.md)
> - **French**: [`docs/user/i18n/fr/docusaurus-plugin-content-docs/current/tutorials/add-an-application.md`](docs/user/i18n/fr/docusaurus-plugin-content-docs/current/tutorials/add-an-application.md)

---

---

## Table of Contents

1. [Step 1: Audit & Eligibility Check (Rules 7, 9 & 10)](#step-1-audit--eligibility-check-rules-7-9--10)
2. [Step 2: Prior Consultation & Approval (Rule 1)](#step-2-prior-consultation--approval-rule-1)
3. [Step 3: Docker Configuration & Secrets as Code (Rules 2 & 5)](#step-3-docker-configuration--secrets-as-code-rules-2--5)
4. [Step 4: Traefik Reverse Proxy & Authentik SSO (Rule 6)](#step-4-traefik-reverse-proxy--authentik-sso-rule-6)
5. [Step 5: Cloudflare Zero Trust IaC Registration (Terraform) (Rule 9)](#step-5-cloudflare-zero-trust-iac-registration-terraform-rule-9)
6. [Step 6: Application Dashboard Metadata (Rule 6)](#step-6-application-dashboard-metadata-rule-6)
7. [Step 7: Gatus GitOps Health Monitoring (Rule 9)](#step-7-gatus-gitops-health-monitoring-rule-9)
8. [Step 8: Automated Empirical Validation & Documentation (Rule 3)](#step-8-automated-empirical-validation--documentation-rule-3)

---

## Step 1: Audit & Eligibility Check (Rules 7, 9 & 10)

Before adding any component:
- **Registry & Version Query (Rules 7 & 10)**: Query container registry APIs (Docker Hub, GHCR, Quay) to fetch and verify the exact **latest stable release version tag** and its **multi-architecture index SHA256 digest** (`docker buildx imagetools inspect <repo>:<tag>`). Every container image declared in `docker-compose.yml` MUST be pinned by its multi-architecture digest with the release tag in a trailing comment: `image: <repo>@sha256:<digest> # <tag>`. Floating tags and `:latest` are strictly forbidden.
- **GitOps-Native & Database-Agnostic Selection (Rule 9)**: Ensure the proposed service is 100% declarative via mounted YAML, JSON, or HCL configuration files. Reject tools requiring GUI setup wizards or custom database seeding scripts.
- **Requirements check**:
  - Identify the internal TCP port it exposes (for example, `:8080`).
  - Determine its persistent storage volume needs.
  - Identify the authentication mechanisms it supports (native OIDC/OAuth2, or Forward Auth via HTTP headers).

---

## Step 2: Prior Consultation & Approval (Rule 1)

Per **Rule 1**, any change to the stack requires prior agreement:
- Write up and present the integration plan (service name, subdomain `https://<service>.<domain>`, internal port, assigned SSO role).
- **Wait for explicit user approval** before editing configuration files or starting containers.

---

## Step 3: Docker Configuration & Secrets as Code (Rules 2 & 5)

### 1. Declare the service in [`docker-compose.yml`](docker-compose.yml)

```yaml
  my-app:
    image: vendor/my-app@sha256:468c25f35f3e5ec4e414974f00deab93337b1b4d9953cabcfd3722e59415f834 # 1.0.0
    container_name: my-app
    restart: unless-stopped
    networks:
      - backend
      - traefik_proxy
    environment:
      PORT: "8080"
      MYAPP_SECRET: "${MYAPP_SECRET}"
    volumes:
      - myapp_data:/var/lib/myapp
    deploy:
      resources:
        limits:
          memory: 512M
```

### 2. Declare the persistent volume (if needed)

```yaml
volumes:
  myapp_data:
    driver: local
```

### 3. Dynamically generate secrets in [`setup.sh`](setup.sh) and [`.env.example`](.env.example)

Never hardcode a fallback value in `docker-compose.yml` (`"${MYAPP_SECRET:-some_default}"`) -
that would violate Rule 5 (zero fallback secrets) the moment a real deployment's `.env` is
ever missing the variable, silently running with a well-known, publicly-visible-in-this-repo
default instead of failing loudly. Use a bare `"${MYAPP_SECRET}"` instead (as above) - Compose
prints an explicit `"MYAPP_SECRET" variable is not set` warning and the container gets an
empty value, both far easier to notice and fix than a silently-working weak secret.

In `setup.sh`, add one `case` line to `generate_secret_value()` and one entry to
`GENERATED_SECRET_NAMES` (both defined right before `generate_env()`):
```bash
# in generate_secret_value()'s case statement:
MYAPP_SECRET) openssl rand -hex 32 ;;
```
```bash
# in GENERATED_SECRET_NAMES:
GENERATED_SECRET_NAMES=(
    ...
    MYAPP_SECRET
)
```
This single change is enough for **both** a fresh clone (`generate_env()` picks it up like
every other secret) **and** an existing deployment (`add_missing_secrets()` notices
`MYAPP_SECRET` isn't in the current `.env` yet and appends a freshly-generated value for it
alone, without touching or rotating any other secret already in use by already-provisioned
services) - there's no separate "existing deployment" step to remember or get wrong.
`generate_env()` itself also calls `add_missing_secrets()` as a safety net right after writing
the heredoc below, so even forgetting to add the optional, cosmetic `NAME=${NAME}` line there
(only useful for keeping the generated `.env` file readably grouped by section) still results
in the secret actually landing in `.env` - just appended at the end instead of grouped nicely.

Optional, for a well-organized `.env` file: also add `MYAPP_SECRET=${MYAPP_SECRET}` to the
`cat <<EOF > .env` heredoc inside `generate_env()`, in whichever section fits best.

In `.env.example` (documentation only, never actually read at runtime):
```bash
MYAPP_SECRET=myapp_secret_change_me
```

### 4. If the application needs post-startup provisioning (API calls, SQL), add a `<tool>/provision.sh` script

Anything beyond simple template hydration — calling the app's REST API, running SQL against its
database, seeding an initial admin role or default connection — belongs in its own
`my-app/provision.sh` script, not inline in `setup.sh`. This keeps `setup.sh` thin and each tool's
provisioning logic co-located with its configuration. See
[`clickhouse/provision.sh`](clickhouse/provision.sh),
[`litellm/provision.sh`](litellm/provision.sh),
[`open-webui/provision.sh`](open-webui/provision.sh), [`ollama/provision.sh`](ollama/provision.sh),
and [`authentik/provision.sh`](authentik/provision.sh) for real examples.

Minimal template:
```bash
#!/usr/bin/env bash
# ==============================================================================
# My App - <what this script provisions and why>
# Called once by ../start.sh, right after "docker compose up -d" (or before, if
# it only touches local files and doesn't need the container running).
#
# Requires <ENV_VARS> to be set in the environment (exported by start.sh from
# .env), and must be run from the repo root (docker compose context).
# ==============================================================================

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

echo "Provisioning my-app..."
# ... curl/python3/docker compose exec logic here, idempotent and best-effort
# (use `|| true` on non-critical steps so a transient failure doesn't abort start.sh).
```

Then call it from `start.sh` with a single line, at the appropriate point in the sequence:
```bash
bash "$REPO_DIR/my-app/provision.sh"
```

---

## Step 4: Traefik Reverse Proxy & Authentik SSO (Rule 6)

This stack has two distinct auth patterns, depending on whether the app has its own login page -
see [`authentik/README.md`](authentik/README.md) for the full architecture and a catalogue of
real bugs found integrating each app so far.

### Pattern A: the app has no login of its own (Forward-Auth)

Most admin tools (Grafana, Dozzle, SearXNG, Qdrant Dashboard, SeaweedFS Filer, ...) have
no authentication of their own - Authentik's native forward-auth outpost gates access entirely
at the Traefik layer.

1. **Reverse proxy routing** in [`docker-compose.yml`](docker-compose.yml):
   - Add Traefik labels to your container (`traefik.enable=true`, `traefik.http.routers.<app>.rule=Host(...)`).
   - If behind Authentik Forward-Auth, add `traefik.http.routers.<app>.middlewares=authentik-auth@file`.

2. **Add Provider + Application + Policy Binding entries to `authentik/blueprints/10-forward-auth.yaml`**:
   Add the following entries to `authentik/blueprints/10-forward-auth.yaml` using native Authentik YAML tags (`!Format`, `!Env`, `!KeyOf`, `!Find`):

   ```yaml
     - model: authentik_providers_proxy.proxyprovider
       state: present
       identifiers:
         name: my-app-forward-auth
       id: provider-my-app
       attrs:
         authorization_flow: !Find [authentik_flows.flow, [slug, default-provider-authorization-implicit-consent]]
         invalidation_flow: !Find [authentik_flows.flow, [slug, default-provider-invalidation-flow]]
         mode: forward_single
         external_host: !Format ["https://my-app.%s", !Env DOMAIN]

     - model: authentik_core.application
       state: present
       identifiers:
         slug: my-app
       id: app-my-app
       attrs:
         name: My App
         provider: !KeyOf provider-my-app
         meta_launch_url: !Format ["https://my-app.%s", !Env DOMAIN]
         meta_icon: "https://cdn.jsdelivr.net/gh/selfhst/icons/png/my-app.png"
         meta_description: "My App description."
         meta_publisher: "llm-stack"

     - model: authentik_policies.policybinding
       state: present
       identifiers:
         target: !KeyOf app-my-app
         group: !Find [authentik_core.group, [name, admins]]
         order: 0
       attrs:
         enabled: true
   ```

3. **Register the proxy provider in the embedded outpost**:
   In the same file (`authentik/blueprints/10-forward-auth.yaml`), add the provider reference under the `authentik_outposts.outpost` entry's `providers` list:
   ```yaml
     - model: authentik_outposts.outpost
       state: present
       identifiers:
         name: authentik Embedded Outpost
       attrs:
         providers:
           # ... existing providers ...
           - !KeyOf provider-my-app
   ```
   Because both the proxy provider and outpost are defined in the same tier file, this declarative binding is processed safely without Celery worker race conditions.

4. **Check the app's own trusted-header env vars, if it has any** (e.g. Dozzle's
   `DOZZLE_AUTH_HEADER_*`, Open WebUI's `WEBUI_AUTH_TRUSTED_EMAIL_HEADER`). They must point at
   Authentik's header names - `X-Authentik-Username`, `X-Authentik-Email`, `X-Authentik-Name`,
   `X-Authentik-Groups` - **not** any other convention. A mismatch here causes a generic,
   app-side "Unauthorized" error that looks identical to an RBAC/policy failure - confirmed
   empirically to be an easy misdiagnosis (see `authentik/README.md`'s "Downstream App Header
   Names Must Match" section).

### Pattern B: the app has its own native OIDC login

For apps that are themselves an OIDC Relying Party (Langfuse, LiteLLM, CHouse UI, Vault):

1. **Add Provider + Application + Policy Binding entries to `authentik/blueprints/20-native-oidc.yaml`**:
   Add the following entries to `authentik/blueprints/20-native-oidc.yaml` using native tags:

   ```yaml
     - model: authentik_providers_oauth2.oauth2provider
       state: present
       identifiers:
         name: my-app-oidc
       id: provider-my-app-oidc
       attrs:
         authorization_flow: !Find [authentik_flows.flow, [slug, default-provider-authorization-implicit-consent]]
         invalidation_flow: !Find [authentik_flows.flow, [slug, default-provider-invalidation-flow]]
         client_type: confidential
         client_id: my-app
         client_secret: !Env MYAPP_OIDC_CLIENT_SECRET
         include_claims_in_id_token: true
         # REQUIRED - Authentik defaults this to an empty list, which rejects every single
         # authorization request with a generic "invalid_request" (see authentik/README.md).
         grant_types:
           - authorization_code
           - refresh_token
         redirect_uris:
           - matching_mode: strict
             url: !Format ["https://my-app.%s/auth/callback", !Env DOMAIN]
         property_mappings:
           - !Find [authentik_providers_oauth2.scopemapping, [scope_name, openid]]
           - !Find [authentik_providers_oauth2.scopemapping, [scope_name, profile]]
           - !Find [authentik_providers_oauth2.scopemapping, [scope_name, email]]
           - !Find [authentik_providers_oauth2.scopemapping, [name, llm-stack-groups-scope]]

     - model: authentik_core.application
       state: present
       identifiers:
         slug: my-app
       id: app-my-app-oidc
       attrs:
         name: My App
         provider: !KeyOf provider-my-app-oidc
         meta_launch_url: !Format ["https://my-app.%s", !Env DOMAIN]
         meta_icon: "https://cdn.jsdelivr.net/gh/selfhst/icons/png/my-app.png"
         meta_description: "My App description."
         meta_publisher: "llm-stack"

     - model: authentik_policies.policybinding
       state: present
       identifiers:
         target: !KeyOf app-my-app-oidc
         group: !Find [authentik_core.group, [name, admins]]
         order: 0
       attrs:
         enabled: true
   ```

2. **Add the app's own `AUTH_OIDC_*`/`GENERIC_*`/equivalent environment variables** to its
   service block in `docker-compose.yml` (issuer, client ID/secret, scopes). Check whether the
   app does OIDC **discovery** (fetches `/.well-known/openid-configuration` itself) or uses
   **explicit hardcoded endpoint URLs** - this determines which bug class from
   `authentik/README.md` might apply (trailing-slash discovery bugs only affect
   discovery-based clients).
3. **Generate `MYAPP_OIDC_CLIENT_SECRET` in `setup.sh`** the same way as every other app secret
   (`openssl rand -hex 32`), add it to the `.env` generation block and `.env.example`.

---

## Step 5: Cloudflare Zero Trust IaC Registration (Terraform) (Rule 9)

Whenever a new service exposes a subdomain (e.g. `my-app`), you MUST register the subdomain name in the Cloudflare Terraform module:

1. **Edit [`cloudflare/variables.tf`](cloudflare/variables.tf)** and add `"my-app"` to the `var.subdomains` list:
   ```hcl
   variable "subdomains" {
     type        = list(string)
     description = "List of subdomains to route to Traefik via Cloudflare Tunnel."
     default = [
       # ... existing subdomains ...
       "my-app",
     ]
   }
   ```
2. **Validate Terraform configuration**: Run `make terraform-validate` locally to ensure HCL syntax and variable validation blocks pass.
3. **Apply Terraform (if public Cloudflare Tunnel is active)**: Run `terraform -chdir=cloudflare apply` (Rule 9: automation). This declaratively creates:
   - The DNS CNAME record (`my-app.${DOMAIN} -> <tunnel-id>.cfargotunnel.com`).
   - The Zero Trust Tunnel ingress rule (`my-app.${DOMAIN} -> http://traefik`).
4. **Update `/etc/hosts` printout in [`setup.sh`](setup.sh)**: Add `my-app.${DOMAIN}` to the local DNS resolution line printed at the end of setup.

---

## Step 6: Application Dashboard Metadata (Rule 6)

There is no separate dashboard container to register a tile in - Authentik's own native
Application Dashboard (`/if/user/`) automatically lists every `authentik_core.application`
blueprint entry, filtered per-user by the same Policy Bindings that gate the app's own
forward-auth/OIDC login (see `authentik/README.md`, and the root `README.md`'s [Authentik Application Dashboard](README.md#authentik-application-dashboard-landing-portal--unified-launcher)
entry). Add these `attrs` to the `authentik_core.application` entry created in Step 4:

```yaml
  - model: authentik_core.application
    state: present
    identifiers:
      slug: my-app
    id: app-my-app
    attrs:
      name: My App
      provider: !KeyOf provider-my-app
      meta_launch_url: !Format ["https://my-app.%s", !Env DOMAIN]
      meta_icon: "https://cdn.jsdelivr.net/gh/selfhst/icons/png/my-app.png"
      meta_description: "One-line description of what My App does."
      meta_publisher: "llm-stack"
```

`meta_icon` can point at any absolute URL the user's browser can load - this project uses the
[selfhst/icons](https://github.com/selfhst/icons) CDN (the same icon catalog Homarr/Homepage-style
dashboards use) rather than self-hosting icon files, since dashboard icons are cosmetic, not a
secret or a functional dependency. Check `https://cdn.jsdelivr.net/gh/selfhst/icons/png/<name>.png`
resolves (HTTP 200) before committing; if the app isn't in that catalog, any other stable, public
icon URL works just as well.

---

## Step 7: Gatus GitOps Health Monitoring (Rule 9)

Every new application or infrastructure component MUST be registered in the Gatus GitOps health dashboard ([`gatus/config.yaml.template`](gatus/config.yaml.template)) so it is automatically monitored.

1. **Add the endpoint block** to [`gatus/config.yaml.template`](gatus/config.yaml.template):
   - For web apps / HTTP APIs:
     ```yaml
       - name: My App
         group: Applications
         url: "http://my-app:8080/health"
         interval: 30s
         conditions:
           - "[STATUS] == 200"
     ```
   - For TCP databases / raw TCP services (e.g. Postgres, Redis):
     ```yaml
       - name: My DB
         group: Data & Storage
         url: "tcp://my-db:5432"
         interval: 30s
         conditions:
           - "[CONNECTED] == true"
     ```
2. **Hydrate to runtime config**: Run `./setup.sh` or trigger template hydration, then restart Gatus:
   ```bash
   docker compose restart gatus
   ```

---

## Step 8: Automated Empirical Validation & Documentation (Rule 3)

1. **Functional Audit Suite (`scripts/smoke_test.py`)**:
   - Add a test function `test_myapp()` and register it in `TEST_REGISTRY` in [`scripts/smoke_test.py`](scripts/smoke_test.py).
   - If the new service is an admin tool protected by Forward-Auth, add its subdomain name (e.g. `'my-app'`) to `FORWARD_AUTH_ADMIN_DOMAINS` in [`scripts/smoke_test.py`](scripts/smoke_test.py) so that `RBAC_ANON` and `RBAC_USERS` automatically verify that anonymous users and non-admin users (`alice`) are blocked.
   - Update the expected visible application count in `test_application_dashboard()` in [`scripts/smoke_test.py`](scripts/smoke_test.py).
2. **Update [`README.md`](README.md)**:
   Add a dedicated, numbered section describing the tool, its ports, and its key configuration files.
3. **Dedicated Service README Policy**:
   A dedicated `<service>/README.md` is required whenever a service involves non-trivial provisioning logic, custom authentication integration, or specialized storage/caching architecture (e.g. `authentik/README.md`, `open-webui/README.md`, `seaweedfs/README.md`, `litellm/README.md`, `clickhouse/README.md`). Standard declarative services with no custom lifecycle scripts rely on the root [`README.md`](README.md) Tool Catalog and inline configuration comments.
4. **Git commit**:
   Save the changes with Git:
   ```bash
   git add .
   git commit -m "feat(my-app): deploy my-app with Authentik SSO, Cloudflare IaC & Gatus monitoring"
   ```

