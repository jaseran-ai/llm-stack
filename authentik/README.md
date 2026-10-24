# Authentik (SSO / IdP)

Authentik is this stack's single sign-on identity provider — one login for every admin tool, one
place to manage users/groups/access policies. This document also records the real integration
pitfalls found while wiring each app, since they're the kind of thing that resurfaces the moment
a new app or blueprint is added.

---

## Why Authentik?

The requirement: a single IdP whose groups drive access in every app, without maintaining a
separate admin/user mapping inside each application.

Authentik was chosen over Keycloak (the other major self-hosted "Okta-style" IdP) because:

* **Native forward-auth outposts.** This stack's dominant auth pattern is forward-auth for
  apps with no login of their own (Grafana, Dozzle, SearXNG, SeaweedFS Filer, Qdrant,
  Open WebUI). Authentik has this built in (a "Proxy Provider" in `forward_single`/domain-level
  mode). Keycloak has no equivalent — its historical companion, `keycloak-gatekeeper`, was
  deprecated and archived in 2020 — meaning a third component (`oauth2-proxy`) would be needed.
* **Reliable `groups` OIDC claim**, first-class and well-documented, so group-based roles
  propagate to native-OIDC apps without per-app workarounds.
* **Lower resource footprint.** No Redis required (unlike some other IdPs), reuses this
  project's shared PostgreSQL instance. Keycloak's own docs recommend budgeting 2GB of JVM heap
  alone for "small production" — Authentik's Python/Go stack is comfortably lighter.
* **Real admin UI** for users/groups/policies — the actual feature being sought.

---

## Architecture

* `authentik-server` + `authentik-worker`: same image (`ghcr.io/goauthentik/server`), different
  `command` (`server` vs `worker`). Both are required — the worker handles blueprint
  application, background tasks, and the outpost's async processing.
* `authentik-provision`: an opt-in, one-shot Compose service using that same pinned image. It
  depends on explicit server and worker health checks, reconciles blueprints/outpost/passwords,
  and must exit successfully before `start.sh` configures Vault OIDC. It is force-recreated on
  every stack start but excluded from ordinary `docker compose up` through the `provisioning`
  profile.
* Database: a dedicated `authentik` database on the stack's **shared** PostgreSQL instance (same
  pattern as Langfuse/LiteLLM — see `init-dbs.sql`), not a separate Postgres container.
* **Embedded outpost**: runs inside `authentik-server` itself — no separate outpost container,
  no Docker socket mount needed. Sufficient for this stack's scale; a managed/separate outpost
  would only be needed for a much larger deployment.
* Traefik route `https://authentik.${DOMAIN}` is Authentik's own portal.

The complete executable sequence, diagnostics, validation contract, and rollback procedure are
documented in the root [startup dependency graph](../docs/startup-dependency-graph.md).

### Why a One-Shot Compose Service

Container health only proves that the Authentik processes and PostgreSQL connection are ready.
It does not prove that asynchronous custom blueprints have completed or that the embedded
outpost has reconciled its provider permissions. `authentik-provision` turns those requirements
into a bounded completion gate with an observable exit code.

The job communicates directly with `http://authentik-server:9000` on the Compose network. It
does not mount the Docker socket, call Docker recursively, download dependencies, or use a
custom image. Its Python clients deliberately use only the standard library because the pinned
Authentik runtime image does not include `requests`.

---

## Bootstrap (Declarative Admin Account)

`AUTHENTIK_BOOTSTRAP_EMAIL` / `AUTHENTIK_BOOTSTRAP_PASSWORD` / `AUTHENTIK_BOOTSTRAP_TOKEN` (set
on the **worker** container only — confirmed via Authentik's own docs, these are not read on the
server) declaratively create the `akadmin` superuser and an API token on first startup, avoiding
the interactive setup wizard entirely — matching this project's "no manual UI setup" governance
rule.

---

## Blueprints (Configuration as Code)

Authentik blueprints live in `authentik/blueprints/` and use native Authentik `!Env` and `!Format`
YAML tags evaluated directly inside the container at runtime. No host-side Python templating,
hydration scripts, or duplicate `.template` files are used. The blueprints are organized into
three consolidated, dependency-ordered tiers:

* **`00-core-identity.yaml`**: Core RBAC groups (`admins`, `users`), standard user accounts
  (`akadmin`, `admin`, `alice`, `bob`), shared OIDC scope mappings (`groups`, `email_verified`),
  and the default brand domain.
* **`10-forward-auth.yaml`**: All 11 Forward-Auth Proxy Providers, their Applications, RBAC Policy
  Bindings, and the Embedded Outpost (`authentik_outposts.outpost`). Because all providers and the
  outpost are co-located in a single file, Authentik applies them in a single atomic transaction,
  eliminating concurrent worker deadlocks and race conditions.
* **`20-native-oidc.yaml`**: All 4 Native OIDC application providers (Langfuse, LiteLLM, CHouse UI,
  Vault), custom scope mappings (e.g. `litellm_role`), and their policy bindings.

**Critical gotcha, confirmed empirically**: these blueprint files are mounted at
`/blueprints/custom/` inside the containers, **not** directly at `/blueprints/`. The official
image ships built-in system/default blueprints (default flows, the admin-bootstrap blueprint,
provider scope mappings, etc.) at that exact path — mounting a volume directly over `/blueprints`
**shadows and destroys them entirely**. The very first attempt at this did exactly that: the
`akadmin` bootstrap user was never created, and the worker logged
`BlueprintRetrievalFailed: [Errno 2] No such file or directory: '/blueprints/system/bootstrap.yaml'`.

Blueprint apply is **asynchronous**, not synchronous with container startup — a freshly
discovered blueprint sits in `unknown` status for several seconds before settling to
`successful`. `authentik/provision.sh` polls each custom blueprint's status through the internal
Compose API endpoint rather than assuming it's already applied once the container reports healthy.

### Declarative Outpost & Provider Binding

The Outpost↔Provider assignment (which Proxy Providers the embedded outpost actually serves) is
declared natively in `10-forward-auth.yaml` using the `authentik_outposts.outpost` model:

```yaml
- model: authentik_outposts.outpost
  state: present
  identifiers:
    managed: goauthentik.io/outposts/embedded
  attrs:
    name: authentik Embedded Outpost
    config:
      authentik_host: !Format ["https://authentik.%s", !Env DOMAIN]
    providers:
      - !KeyOf provider-dozzle
      - !KeyOf provider-grafana
      # ... all 11 providers referenced via compile-time !KeyOf
```

Because updating the outpost triggers asynchronous route table synchronization in the embedded Go
daemon, `authentik/scripts/wait_for_outpost.py` probes the Forward-Auth endpoint with a representative
protected host until it returns the expected unauthenticated redirect to `https://authentik.${DOMAIN}`.
This guarantees that startup reports success only after the embedded outpost route table is active.

---

## The Embedded Outpost's Browser-Facing URL (a Real Bug)

Two separate configuration values needed correcting before OAuth redirects worked, both
confirmed empirically:

1. **`authentik_host` on the embedded outpost.** Despite Authentik's own YAML config reference
   marking `authentik_host`/`authentik_host_browser` as "only relevant when using a managed
   outpost", the *embedded* outpost's docs explicitly say to set `authentik_host` after
   installation "because authentik does not know its own primary URL." Left unset (or set to
   the container's internal Docker hostname), the `/application/o/authorize/...` redirect sent
   to the browser pointed at `http://authentik-server:9000/...` — unreachable from any browser.
   Fixed by declaring it as `!Format ["https://authentik.%s", !Env DOMAIN]` in `10-forward-auth.yaml`.
2. **The default Brand's own `domain` field**, which defaults to a placeholder
   (`authentik-default`) and is used when constructing some absolute OAuth2 URLs — also
   declared as `!Format ["authentik.%s", !Env DOMAIN]` in `00-core-identity.yaml`.

---

## A Second Real Bug: Downstream App Header Names Must Match

Wiring Dozzle surfaced a second, unrelated bug that looked identical to an
RBAC/policy failure at first: after fully fixing the OAuth flow above, an authenticated,
correctly-group-authorized user still got a plain-text `Unauthorized user` response (**not** an
Authentik-branded error page — the tell that it wasn't Authentik rejecting the request at all).

Root cause: Dozzle's own `DOZZLE_AUTH_PROVIDER=forward-proxy` mode reads specific header names,
configured in `docker-compose.yml` via `DOZZLE_AUTH_HEADER_USER`/`_EMAIL`/`_NAME`. Their
defaults follow the common `Remote-User`/`Remote-Email`/`Remote-Name` convention, but
Authentik's forward-auth outpost sends **differently named** headers
(`X-Authentik-Username`, `X-Authentik-Email`, `X-Authentik-Name`, `X-Authentik-Groups`, ...).
Dozzle never received the header it expected and rejected every request with its own generic
error — easy to misdiagnose as a policy/RBAC problem since the symptom (401, "Unauthorized")
looks superficially similar.

**Every app behind the `authentik-auth` Traefik middleware must have its own downstream
header-name configuration checked** (if it has one) — this is not a one-time fix, it applies
per app.

---

## Native-OIDC Apps: Universal Pitfalls

Native-OIDC apps call `/application/o/authorize/` and the token endpoints themselves, which
exposes two pitfalls that forward-auth apps never hit:

1. **Server-to-server calls to `authentik.${DOMAIN}` must resolve inside Docker.** OIDC
   discovery and token requests are made *from the app container*, not the browser. The
   `traefik` service therefore declares Docker network aliases for the public hostnames
   (`authentik.${DOMAIN}`, `chat.${DOMAIN}`, ...) so these calls reach Traefik without a real DNS
   server. A missing alias shows up as `getaddrinfo ENOTFOUND authentik.<domain>` in the app's
   logs.
2. **`grant_types` defaults to an empty list on `authentik_providers_oauth2.oauth2provider`.**
   Without explicitly setting it in the blueprint, Authentik silently accepts the provider but
   rejects **every single** `/application/o/authorize/?response_type=code...` request with a
   generic `invalid_request - The request is otherwise malformed` (confirmed via
   `authentik/providers/oauth2/views/authorize.py`'s `check_grant()`: `"authorization_code" not
   in self.provider.grant_types`, since that list is empty). Forward-auth (Proxy) providers never
   hit this code path. Fixed by adding `grant_types: [authorization_code, refresh_token]` to the
   OAuth2Provider blueprint entry — required for **every** native-OIDC app blueprint.

---

## Native-OIDC Apps, Round Two: Three More Real Bugs (Langfuse)

Langfuse (NextAuth v4 + `openid-client@5.7.1`) surfaced three further bugs:

1. **A trailing slash on the issuer causes a double-slash discovery URL that isn't followed.**
   Langfuse builds its OIDC discovery URL as a **plain string concatenation**:
   `` `${issuer}/.well-known/openid-configuration` `` (confirmed by decompiling Langfuse's own
   bundled server code) - it does not check whether `issuer` already ends in `/`. Authentik's
   per-provider issuer URLs always end in `/` (e.g. `.../application/o/langfuse/`), so this
   produces `.../application/o/langfuse//.well-known/openid-configuration` (double slash). A
   reverse proxy that normalizes the path answers with a `301 Moved Permanently` - which
   `openid-client@5.7.1`'s `Issuer.discover()` does **not** follow (it requires exactly `200 OK`
   on the first response), failing with a generic, unhelpful `SIGNIN_OAUTH_ERROR` that Langfuse's
   own logger drops the underlying exception detail for by default (see below for how to see it).
   Fixed by configuring `AUTH_CUSTOM_ISSUER` **without** a trailing slash - the resulting single
   `/` in the concatenated URL is exactly what Authentik expects, and the discovered `issuer`
   claim (which Authentik still returns *with* its own trailing slash) is not compared
   byte-for-byte against the configured value in this flow, so there's no mismatch either.
   **This bug class is specific to OIDC-discovery-based clients that don't normalize trailing
   slashes**. Confirmed this does **not** affect LiteLLM: it doesn't do OIDC
   discovery at all (explicit, hardcoded `GENERIC_*_ENDPOINT` env vars), so it migrated cleanly
   with no bugs of its own beyond the universal `grant_types` one.
2. **`unexpected JWT alg received, expected RS256, got: HS256`.** `openid-client` defaults to
   expecting `RS256`-signed ID tokens unless the client is explicitly configured otherwise -
   it does **not** trust the discovery document's own `id_token_signing_alg_values_supported`
   (which correctly advertises `HS256`, since our OAuth2Provider has no RSA `signing_key`
   configured). Fixed by setting `AUTH_CUSTOM_ID_TOKEN_SIGNED_RESPONSE_ALG=HS256` - an
   `openid-client`-specific quirk.
3. **`OAuthAccountNotLinked`.** When the same human (`admin@example.com`) is re-provisioned (for
   example after the Authentik provider is recreated), they arrive with a **different OAuth
   `sub`** under the same Langfuse
   provider id (`"custom"`) - Auth.js treats this as an unrelated, unlinked account by default and
   refuses to sign in, even though the e-mail matches an existing user. Fixed by setting
   `AUTH_CUSTOM_ALLOW_ACCOUNT_LINKING=true` (this is the standard, expected fix whenever a
   user's OAuth `sub` changes for any reason - not itself a bug, but easy to miss until you hit
   it).

**Debugging tip confirmed empirically:** Langfuse's own logger silently drops the `error` object
passed to `logger.error(event, error)` for `[NEXT_AUTH]` events unless `LANGFUSE_LOG_FORMAT=json`
is set (the default pretty-printer only prints the message string, not the metadata). Temporarily
setting `LANGFUSE_LOG_FORMAT=json` (and `LANGFUSE_LOG_LEVEL=debug`) surfaced the full stack trace
for all three bugs above; both were removed again once diagnosed, they are not needed permanently.

---

## Blueprint Apply Concurrency: A Postgres Deadlock (Not a Content Bug)

Applying several blueprints **concurrently** (e.g. right after they are all freshly discovered
together, or when re-triggered via the API in a tight loop with no delay) reliably causes
Postgres deadlocks — confirmed via each failed apply task's own log entry: `deadlock detected ...
while deleting tuple in relation guardian_role(object|model)permission`. Applying a
Provider/Application rebuilds Guardian object permissions, which touches overlapping database
rows across blueprints running in parallel transactions. The apply task itself catches the
exception and marks the blueprint `error` — **it is not automatically retried by Authentik**.

This is purely a concurrency artifact, not a problem with the blueprint's actual content: the
underlying config from the *previous* successful apply remains intact and the app keeps working
even while its blueprint shows `error` (confirmed empirically — Grafana/Qdrant kept
returning `200` throughout). `authentik/provision.sh` handles this automatically: if, after all
blueprints have settled out of `unknown`, any are left in `error`, it re-applies just those,
**one at a time with a delay in between**, until every custom blueprint reports `successful`.

---

## Traefik Forward-Auth Middleware

`traefik/dynamic.yml.template` declares the `authentik-auth` middleware following the
[official Traefik forward-auth pattern](https://docs.goauthentik.io/add-secure-apps/providers/proxy/server_traefik):
a `forwardAuth` call to the embedded outpost at
`http://authentik-server:9000/outpost.goauthentik.io/auth/traefik`, copying the `X-Authentik-*`
response headers to the upstream request. Protecting a new app means adding `authentik-auth` to
its router's middlewares (see `../ADDING_AN_APPLICATION.md`).

---

## Native-OIDC Apps, Round Three: Two More Real Bugs (CHouse UI)

CHouse UI, like LiteLLM, uses explicit hardcoded `AUTHORIZATION/TOKEN/USERINFO_ENDPOINT` env vars
(no OIDC discovery), so it isn't affected by the `openid-client` bugs above. Two new things found:

1. **CHouse UI's OIDC client (`oauth4webapi`) refuses plain HTTP requests by default**
   (`OAUTH_HTTP_REQUEST_FORBIDDEN`) - unlike LiteLLM, whose token/userinfo endpoints go straight
   to the internal `http://authentik-server:9000/...` (bypassing Traefik/TLS entirely). CHouse
   UI's token/userinfo endpoints had to go through `https://authentik.${DOMAIN}/...` (Traefik/TLS)
   instead.
2. **`AUTH_SSO_AUTO_LINK_BY_EMAIL` silently refuses to link unless the IdP claims a verified
   e-mail.** CHouse UI's own SSO code path only attempts to link an incoming OIDC login to an
   existing user *by e-mail* when `identity.emailVerified` is truthy (confirmed by decompiling
   its bundled server code: `if (!user && config.autoLinkByEmail && identity.email &&
   identity.emailVerified)`) - otherwise it falls through to *creating a new user*, which then
   fails with a `UNIQUE constraint failed: rbac_users.email` for any user that already exists.
   Authentik's own built-in `email` scope mapping hardcodes `"email_verified": False`
   unconditionally (confirmed via the API) and cannot be edited in place (it's a shared system
   mapping used by every provider). Fixed with a new custom scope mapping,
   `authentik/blueprints/00-core-identity.yaml`
   (`llm-stack-email-verified-scope`), which **replaces** (not supplements) the default `email`
   mapping on CHouse UI's provider only, setting `"email_verified": true`. This is not a security
   downgrade for this stack: there is no self-registration or e-mail verification stage at all
   (users are provisioned declaratively via blueprints) - the claim is simply always true for
   every account that exists. Langfuse never hits this because its account-linking flag
   (`AUTH_CUSTOM_ALLOW_ACCOUNT_LINKING`) doesn't gate on `email_verified` at all.

---

## Apps & Access Control

| App | Mechanism | Access | Notes |
| :--- | :--- | :--- | :--- |
| Dozzle | Forward-auth outpost | `admins` only | `DOZZLE_AUTH_HEADER_*` env vars must match Authentik's `X-Authentik-*` header names. |
| Grafana | Forward-auth outpost | `admins` only | `GF_AUTH_PROXY_HEADER_NAME=X-Authentik-Username`. |
| SearXNG | Forward-auth outpost | `admins` only | No app-level header config - pure forward-auth gate. |
| SeaweedFS Filer Console (`s3-console`) | Forward-auth outpost | `admins` only | No app-level header config. Not to be confused with the SigV4 S3 API (`s3.${DOMAIN}`), which has no forward-auth at all. |
| Qdrant Dashboard | Forward-auth outpost | `admins` only | No app-level header config - pure forward-auth gate. |
| Open WebUI | Forward-auth outpost | `admins` **and** `users` | `WEBUI_AUTH_TRUSTED_EMAIL_HEADER`/`WEBUI_AUTH_TRUSTED_NAME_HEADER=X-Authentik-Email`/`X-Authentik-Name`. The only forward-auth app open to both groups (two Policy Bindings, evaluated as OR) - every other one is `admins`-only. |
| Langfuse | Native OIDC (NextAuth v4 / `openid-client`) | `admins` only | `AUTH_CUSTOM_ISSUER` **without** a trailing slash, `AUTH_CUSTOM_ID_TOKEN_SIGNED_RESPONSE_ALG=HS256`, `AUTH_CUSTOM_ALLOW_ACCOUNT_LINKING=true`. |
| LiteLLM | Native OIDC (`GENERIC_*` env vars, no discovery) | `admins` only | Token/userinfo point directly at `http://authentik-server:9000/...` (internal, bypassing Traefik/TLS). |
| CHouse UI | Native OIDC (`AUTH_SSO_PROVIDERS_AUTHENTIK_*` env vars, no discovery) | `admins` only | Token/userinfo go through `https://authentik.${DOMAIN}/...` (Traefik/TLS) - its OIDC client refuses plain HTTP. Needs the `llm-stack-email-verified-scope` mapping for account auto-linking. |

---

## Test Credentials

| Username | Password | Groups |
| :--- | :--- | :--- |
| `admin` | Generated `UI_PASSWORD` from `.env` | `admins`, `users` |
| `alice` | Generated `ALICE_PASSWORD` from `.env`, seeded into Vault KV v2 | `users` |
| `bob` | Generated `BOB_PASSWORD` from `.env`, seeded into Vault KV v2 | `users` |

`./setup.sh` generates these credentials once for each installation. Authentik's user blueprint
does not contain them: Vault Agent renders them into `vault/secrets_ram/authentik.env`, and the
one-shot provisioning gate reconciles the accounts through the Authentik API. Existing `.env`
values are preserved on subsequent setup runs; production account rotation requires a
separate approved change.
