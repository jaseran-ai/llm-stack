# Reference: Public API Specification

This reference details the public REST API endpoints exposed by the LLM Stack. This specification is automatically derived from the live gateway and contains only endpoints tagged with `x-llm-stack-audience: public`.

> **Machine-Readable Spec**: [`openapi-public.json`](openapi-public.json)

---

## Base Ingress URL

```text
https://chat.${DOMAIN}/api
https://litellm.${DOMAIN}/v1
```

All requests require authentication via a Bearer token:
```text
Authorization: Bearer <LITELLM_MASTER_KEY>
```

---

## 1. List Models (`GET /v1/models`)

Returns the list of currently active model identifiers and routing aliases.

* **Method**: `GET`
* **Path**: `/v1/models`
* **Response**: `HTTP 200 OK`
```json
{
  "object": "list",
  "data": [
    {
      "id": "lfm2.5-thinking-1.2b",
      "object": "model",
      "owned_by": "llm-stack"
    }
  ]
}
```

---

## 2. Create Chat Completion (`POST /v1/chat/completions`)

Submits a prompt for generation with automatic PII and secret redaction.

* **Method**: `POST`
* **Path**: `/v1/chat/completions`
* **Payload**:
```json
{
  "model": "lfm2.5-thinking-1.2b",
  "messages": [
    {"role": "user", "content": "Explain zero-trust architecture in one paragraph."}
  ],
  "temperature": 0.7,
  "stream": false
}
```
* **Response**: `HTTP 200 OK` (Standard OpenAI ChatCompletion object).

---

## 3. Create Text Embeddings (`POST /v1/embeddings`)

Generates a vector embedding for semantic indexing and search.

* **Method**: `POST`
* **Path**: `/v1/embeddings`
* **Payload**:
```json
{
  "model": "text-embedding-nomic",
  "input": "Document text chunk to vectorize"
}
```
* **Response**: `HTTP 200 OK` (Array of floating-point embedding coordinates).

---

## 4. Health Check (`GET /healthz`)

Public liveness and readiness probe for load balancers.

* **Method**: `GET`
* **Path**: `/healthz`
* **Response**: `HTTP 200 OK` (`{"status": "ok"}`).
