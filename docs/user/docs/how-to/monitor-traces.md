# How-To: Inspect Prompts and Execution Traces in Langfuse

This guide explains how to use Langfuse to trace prompt lifecycles, monitor latency, and track token spend across models.

---

## Accessing Langfuse

1. Navigate to the Langfuse web interface:
   ```text
   https://langfuse.${DOMAIN}
   ```
2. Click **Sign in with Authentik (SSO)**.
3. Authenticate with your administrative credentials. You are automatically provisioned into the default project (`llm-stack-project`).

---

## Exploring Traces

* **Traces Dashboard**: Displays every request processed by LiteLLM or Open WebUI, including input prompts, output completions, latency in milliseconds, and token usage.
* **Span Waterfall Graphs**: Shows the exact breakdown of time spent during prompt preprocessing, vector retrieval (RAG), PII redaction (Betterleaks), and raw model inference.
* **Model Cost Tracking**: Provides real-time charts calculating aggregate token consumption and cost estimations partitioned by model tier.
* **Scores and Evaluations**: Enables automated or human-in-the-loop scoring of model generations for quality and factual accuracy.
