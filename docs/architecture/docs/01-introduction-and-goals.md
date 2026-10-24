# 1. Introduction and Goals

This document describes the software architecture of the **LLM Stack**, an enterprise-grade, self-hosted platform providing unified serving, governance, observability, and security for Large Language Models.

---

## 1.1 Requirements Overview

The LLM Stack satisfies three core functional requirements:
1. **Interactive Chat & Knowledge Retrieval (RAG)**: A feature-rich user interface (Open WebUI) allowing end users to converse with LLMs, upload documents for semantic search (Qdrant), and perform real-time private web searches (SearXNG).
2. **Unified Model Gateway & Guardrails**: An OpenAI-compatible gateway (LiteLLM) providing virtual keys, budgets, and fallbacks, combined with bidirectional secret and PII redaction (Betterleaks + Presidio).
3. **Comprehensive LLMOps Observability**: Full traceability of prompt lifecycles, latency, token spend, and evaluation scores (Langfuse) coupled with cluster-wide metrics (Prometheus), real-time logs (Loki), and declarative health probes (Gatus).

---

## 1.2 Quality Goals

| Priority | Goal | Description |
|---|---|---|
| **1** | **Deterministic Reproducibility** | The entire platform can be deployed from a fresh clone in a single automated step (`./setup.sh`) without manual GUI interaction or uncommitted database edits. |
| **2** | **Zero-Trust Security by Default** | Strict perimeter isolation, no exposed plaintext database ports, in-memory secret isolation (Vault tmpfs), and mandatory SSO/RBAC across all endpoints. |
| **3** | **Portability & Resource Efficiency** | Out-of-the-box local CPU inference (`lfm2-1.2b-rag`) ensuring the entire stack runs autonomously on a single laptop, VM, or homelab without GPU hardware requirements. |
| **4** | **Empirical Verifiability** | Every feature, security boundary, and RBAC constraint is automatically validated by regression test suites (`./smoke_test.sh` 28/28 tests passing). |

---

## 1.3 Stakeholders

| Role | Contact / Persona | Expectations |
|---|---|---|
| **Platform Engineer / Integrator** | System Administrator | Fast, automated setup, declarative GitOps workflows, zero configuration drift, clear backup/recovery procedures. |
| **AI Developer / Agent Engineer** | Application Developer | Standardized OpenAI-compatible endpoints, rich Model Context Protocol (MCP) tool exposure, automatic PII protection, detailed execution traces. |
| **Security Auditor** | Compliance Officer | Zero unencrypted secrets on disk, verifiable TLS certificates without bypass flags, least-privilege IAM, audit trails, and strict RBAC. |
| **End User** | Business User | Intuitive chat UI, instant document querying, fast response streaming, high availability. |
