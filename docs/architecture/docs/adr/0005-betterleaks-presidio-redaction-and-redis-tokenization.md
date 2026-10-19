# ADR 0005: Betterleaks Presidio Redaction and Redis Tokenization

* **Status**: Accepted
* **Deciders**: LLM Stack maintainers
* **Date**: 2026-09-25
* **Technical Story**: Bidirectional secrets interception and reversible tokenization

## Context and Problem Statement

When developers and applications interact with LLMs, sensitive information (API keys, private tokens, passwords, and Personally Identifiable Information) can inadvertently be leaked in prompts or echoed in completions. Simple regex masking (`[REDACTED]`) breaks code syntax and prevents downstream automated tools from functioning with the original values.

## Decision Drivers

* High-speed, low-latency detection of secrets and PII (both English and French).
* Bidirectional protection (incoming prompts and outgoing model responses).
* Reversible vaulted tokenization allowing developers to inspect sanitized payloads while restoring original values when needed.
* Zero-trust encryption for the token storage backend.

## Considered Options

1. **Heavy PyTorch Guardrails (e.g., Llama-Guard / NeMo)**: Requires multi-gigabyte GPU models, conflicting with CPU-only portability.
2. **One-Way Masking**: Replaces text with static placeholders; destroys code structure and prevents bidirectional tool execution.
3. **Betterleaks Go Engine + Presidio Analyzer with AES-256-GCM Redis Storage**: Lightweight Go binary for pattern matching, spaCy small models for NER, and surrogate token mapping stored in Redis encrypted with AES-256-GCM.

## Decision Outcome

Chosen option: **Betterleaks + Presidio with Reversible AES-256-GCM Tokenization**, integrated via Open WebUI outlet filter and LiteLLM callback guardrails, with an optional ExtMcp gRPC endpoint for MCP gateways.

### Positive Consequences

* Secrets and PII are redacted before prompts reach the LLM or third-party providers.
* Reversible tokenization allows authenticated clients to restore original secrets securely.
* Token mappings in Redis are encrypted client-side; a dump of Redis reveals only ciphertext.
* Dedicated Prometheus metrics and Alertmanager rules trigger on detected leak events.

### Negative Consequences

* Introduces a small latency overhead on chat completions (~15-30ms for local NLP inspection).
