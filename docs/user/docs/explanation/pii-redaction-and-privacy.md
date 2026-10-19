# Explanation: PII Redaction & Reversible Vaulted Tokenization

This document explains the architecture of the platform's in-flight privacy guardrails and tokenization system.

---

## The Challenge: Privacy vs. Developer Utility

When developers or business applications interact with AI models:
* Pasting raw credentials or sensitive personal information into prompts creates compliance breaches (GDPR, HIPAA, SOC 2) and risks data exfiltration.
* However, simple masking (`[REDACTED]`) breaks downstream code and prevents automated pipelines from receiving usable outputs.

---

## Dual-Engine Detection Pipeline

The LLM Stack implements a two-stage hybrid redaction pipeline in `betterleaks-presidio`:

### 1. High-Speed Pattern Scanning (Betterleaks Engine)
A compiled Go microservice scans input text against thousands of regular expression signatures targeting:
* Cloud provider credentials (AWS, GCP, Azure).
* Secret tokens (GitHub, Slack, Stripe, OpenAI).
* Cryptographic private keys (RSA, Ed25519, PEM certs).

### 2. Contextual Named Entity Recognition (Presidio Analyzer)
A Python service powered by spaCy NLP models analyzes natural language context to identify:
* Person names (`PERSON`).
* Email addresses (`EMAIL_ADDRESS`).
* Phone numbers (`PHONE_NUMBER`).
* Physical addresses and IBAN numbers.
* Models are loaded for both **English** (`en_core_web_sm`) and **French** (`fr_core_news_sm`).

---

## Reversible Vaulted Tokenization

Rather than destroying sensitive data, the service implements **Reversible Vaulted Tokenization**:

1. **Surrogate Substitution**: An API key like `ghp_ABC123456789` is swapped for a randomized surrogate token: `<SURROGATE_TOKEN_API_KEY_01>`.
2. **Client-Side AES-256-GCM Encryption**: The mapping between `ghp_ABC123456789` and `<SURROGATE_TOKEN_API_KEY_01>` is encrypted using a 256-bit AES key fetched from HashiCorp Vault.
3. **Encrypted Ephemeral Store**: The ciphertext is stored in Redis with an automatic Time-To-Live (TTL). Even if the Redis cache is dumped, no plaintext secrets are revealed.
4. **De-anonymization**: When the model finishes responding, an authorized client can call `/v1/deanonymize` to restore the original value transparently.
