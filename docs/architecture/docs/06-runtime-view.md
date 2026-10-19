# 6. Runtime View

This section details the dynamic execution behavior and sequence flows for critical runtime scenarios.

---

## 6.1 Scenario 1: User Authentication via Forward-Auth (Pattern A)

When an end-user navigates to an administrative tool (e.g. Open WebUI, Grafana, Dozzle), Traefik intercepts the request and evaluates authentication against Authentik before routing upstream:

![SSO Forward-Auth Flow](@site/docs/diagrams/svg/sso-forward-auth.svg)

### Sequence Description
1. User requests `https://chat.{DOMAIN}/` via browser.
2. Traefik intercepts the request and executes an internal sub-request to the embedded Authentik outpost (`/outpost.goauthentik.io/auth/traefik`).
3. If valid session cookies are present and the user belongs to the authorized group (`admins` or `users`), the outpost returns `HTTP 200` with identity headers (`X-authentik-username`, `X-authentik-email`).
4. Traefik injects the verified identity headers and forwards the request upstream to the Open WebUI container.
5. If unauthenticated, the outpost returns `HTTP 401/302`, redirecting the browser to Authentik's login flow.

---

## 6.2 Scenario 2: LLM Completion with Betterleaks PII Redaction & Vaulted Tokenization

When a client submits a chat completion, the prompt is intercepted, scanned, and redacted prior to execution, and the response is safe-guarded:

![LLM Completion Guardrail Flow](@site/docs/diagrams/svg/llm-completion-guardrail.svg)

### Sequence Description
1. Client submits a prompt containing sensitive data (e.g. an API key or email) to LiteLLM's `/v1/chat/completions` endpoint.
2. LiteLLM triggers a pre-call guardrail hook calling Betterleaks Presidio (`/v1/anonymize`).
3. Betterleaks runs regex detection and spaCy NER classification.
4. Detected sensitive entities are replaced with randomized surrogate tokens (e.g. `<SURROGATE_TOKEN_API_KEY_01>`).
5. Betterleaks encrypts the original-to-surrogate mapping with **client-side AES-256-GCM** using keys fetched from Vault, storing the ciphertext in Redis with a TTL.
6. The sanitized prompt is dispatched to the inference backend (Ollama or external provider).
7. The inference engine generates a completion referencing only the surrogate token.
8. LiteLLM executes a post-call hook calling Betterleaks (`/v1/deanonymize`).
9. Betterleaks retrieves and decrypts the mapping from Redis, restores the original value for authorized clients, and streams the clean response to the user.

---

## 6.3 Scenario 3: S3 Object Ingestion via Scoped SigV4 IAM

When Langfuse exports traces or Open WebUI uploads documents:
1. The application reads scoped S3 credentials (`LANGFUSE_S3_ACCESS_KEY` / `LANGFUSE_S3_SECRET_KEY`) from the in-memory tmpfs mount (`/vault/secrets_ram/langfuse.env`).
2. The application computes standard AWS SigV4 authorization signatures scoped strictly to the target bucket (`langfuse`).
3. SeaweedFS verifies the SigV4 signature against the internal IAM identity generated during `setup.sh`.
4. The request succeeds because the identity holds explicit `Read:langfuse`, `Write:langfuse`, and `List:langfuse` actions. Any attempt to traverse to administrative endpoints or other buckets is blocked with `HTTP 403 Forbidden`.
