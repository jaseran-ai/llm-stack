# Concept Explanations

The Explanation section provides conceptual overviews, architecture rationale, and deeper discussions of the design philosophies behind the LLM Stack.

---

* [**Explanation: PII Redaction & Reversible Vaulted Tokenization**](pii-redaction-and-privacy.md)
  How dual-engine detection (regex + spaCy NER) and client-side AES-256-GCM encryption protect sensitive data.

* [**Explanation: Zero-Trust Security & In-Memory Secrets**](zero-trust-model.md)
  How the platform enforces zero-disk secret persistence, internal TLS, and strict least-privilege IAM.
