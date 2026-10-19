# Reference: Supported Models & Parameters

This document specifies the default bundled inference models and external providers supported by LiteLLM.

---

## 1. Bundled Local CPU Model

The stack includes a local inference backend running inside the `ollama` container.

* **Model Name**: `lfm2.5-thinking:1.2b`
* **Model Alias**: `lfm2.5-thinking-1.2b`
* **Parameters**: 1.2 Billion parameters
* **Quantization**: Q4_K_M GGUF format
* **Hardware Requirements**: Runs entirely on host CPU (consumes ~1.8 GB RAM). No GPU required.
* **Intended Use**: Fast reasoning, system status explanations, prompt categorization, local development.

---

## 2. Text Embedding Model

* **Model Name**: `nomic-embed-text`
* **Dimensions**: 768
* **Context Length**: 8192 tokens
* **Intended Use**: Document vectorization for Qdrant Knowledge Retrieval (RAG).

---

## 3. Supported External Providers

LiteLLM supports forwarding requests to over 100 cloud providers when configured with appropriate API keys:

| Provider | Supported Models | Configuration Key |
|---|---|---|
| **Anthropic** | Claude 3.5 Sonnet, Claude 3.5 Haiku, Claude 3 Opus | `ANTHROPIC_API_KEY` |
| **OpenAI** | GPT-4o, GPT-4o-mini, o1-preview, o1-mini | `OPENAI_API_KEY` |
| **Google** | Gemini 1.5 Pro, Gemini 1.5 Flash | `GEMINI_API_KEY` |
| **Mistral AI** | Mistral Large 2, Mistral NeMo, Codestral | `MISTRAL_API_KEY` |
| **DeepSeek** | DeepSeek-V3, DeepSeek-R1 | `DEEPSEEK_API_KEY` |

---

## 4. Standard Inference Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `temperature` | float | `0.7` | Randomness of response generation (0.0 = deterministic, 1.0 = creative). |
| `top_p` | float | `0.9` | Nucleus sampling probability cutoff. |
| `max_tokens` | integer | `4096` | Maximum token limit for the generated output completion. |
| `stream` | boolean | `false` | Enable Server-Sent Events (SSE) streaming for real-time tokens. |
