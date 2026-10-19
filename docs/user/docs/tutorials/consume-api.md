# Tutorial: Consume the LLM API with Python and cURL

This tutorial demonstrates how to interact with the unified LiteLLM endpoint from external applications.

---

## 1. Prerequisites

Obtain an API key. You can generate API keys through the LiteLLM administrative interface or read the pre-provisioned master key from the in-memory secrets mount:
```bash
LITELLM_KEY=$(grep "LITELLM_MASTER_KEY=" vault/secrets_ram/litellm.env | cut -d= -f2)
```

---

## 2. Listing Available Models with cURL

Query the `/v1/models` endpoint:
```bash
curl -s -X GET "https://litellm.${DOMAIN}/v1/models" \
  -H "Authorization: Bearer ${LITELLM_KEY}" | jq .
```

Example response:
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

## 3. Submitting a Chat Completion with Python

Use the official `openai` Python SDK (version 1.0+):

```python
import os
from openai import OpenAI

client = OpenAI(
    api_key=os.environ.get("LITELLM_KEY"),
    base_url="https://litellm.example.local/v1"
)

response = client.chat.completions.create(
    model="lfm2.5-thinking-1.2b",
    messages=[
        {"role": "system", "content": "You are a helpful software assistant."},
        {"role": "user", "content": "Write a Python function to compute Fibonacci numbers."}
    ],
    temperature=0.7
)

print(response.choices[0].message.content)
```

---

## 4. Verifying Privacy Guardrails

Submit a prompt containing sensitive data (e.g., an AWS secret key or personal email address):
```bash
curl -s -X POST "https://litellm.${DOMAIN}/v1/chat/completions" \
  -H "Authorization: Bearer ${LITELLM_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "lfm2.5-thinking-1.2b",
    "messages": [
      {"role": "user", "content": "My AWS key is AKIAIOSFODNN7EXAMPLE, can you help me rotate it?"}
    ]
  }'
```

Behind the scenes, Betterleaks Presidio intercepts the prompt, replaces the key with `<SURROGATE_TOKEN_API_KEY_01>`, and verifies that raw credentials never leave the perimeter.
