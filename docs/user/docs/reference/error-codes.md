# Reference: Error Codes & Decisions

This document details the HTTP response codes, error payloads, and guardrail decision indicators returned by LLM Stack endpoints.

---

## 1. HTTP Status Codes

| HTTP Status | Name | Meaning & Trigger | Resolution |
|---|---|---|---|
| **200** | `OK` | Request processed successfully. | Normal response. |
| **400** | `Bad Request` | Malformed JSON payload or missing mandatory parameters (`model`, `messages`). | Check syntax against API reference. |
| **401** | `Unauthorized` | Missing or invalid Bearer token. | Provide a valid API key in `Authorization` header. |
| **403** | `Forbidden` | User lacks group permissions (e.g. non-admin attempting to access Dozzle or CHouse UI). | Verify Authentik group assignment (`admins` vs `users`). |
| **404** | `Not Found` | Requested model or endpoint does not exist. | Query `GET /v1/models` to confirm active aliases. |
| **429** | `Too Many Requests` | Budget quota exceeded or rate limit hit on upstream provider. | LiteLLM automatically triggers fallback model if configured. |
| **500** | `Internal Error` | Upstream failure or container crash. | Inspect logs via Dozzle (`https://logs.${DOMAIN}`). |
| **502 / 503** | `Bad Gateway` | Target service is booting or unhealthy. | Check service status on Gatus dashboard (`https://status.${DOMAIN}`). |

---

## 2. Guardrail Decision Codes

When Betterleaks intercepts a prompt, headers indicate the inspection outcome:

* `X-Betterleaks-Action: pass` — Prompt contained no detectable secrets or PII.
* `X-Betterleaks-Action: anonymize` — Detected entities were sanitized and surrogate tokens injected.
* `X-Betterleaks-Action: block` — Prompt contained a catastrophic leak and was rejected immediately.
