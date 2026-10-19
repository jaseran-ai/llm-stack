# ADR 0006: SeaweedFS Least-Privilege S3 IAM

* **Status**: Accepted
* **Deciders**: LLM Stack maintainers
* **Date**: 2026-10-18
* **Technical Story**: Least-privilege IAM scoping for object storage consumers

## Context and Problem Statement

SeaweedFS provides S3-compatible object storage. Previously, all services (including Langfuse and smoke test scripts) shared the administrative S3 access credentials (`seaweed_admin`), which held global `Admin` permissions across all buckets and filer configurations. A compromise of the Langfuse application would have allowed full deletion or modification of all storage buckets.

## Decision Drivers

* Principle of Least Privilege (PoLP).
* Scope application credentials strictly to their designated bucket (`langfuse`).
* Prevent application access to administrative S3 APIs or filer management endpoints.
* Automated provisioning via Vault KV v2.

## Considered Options

1. **Shared Admin Credentials**: Single key pair for all consumers. Violates security governance.
2. **Per-Bucket MinIO Server Deployment**: Too heavy; violates resource efficiency constraints.
3. **SeaweedFS Declarative Bucket-Scoped IAM**: Configuring a dedicated `langfuse_app` identity with explicit actions (`Read:langfuse`, `Write:langfuse`, `List:langfuse`, `Tagging:langfuse`) without `Admin`, reserving `seaweed_admin` strictly for maintenance.

## Decision Outcome

Chosen option: **SeaweedFS Bucket-Scoped IAM Identity (`langfuse_app`)**, generated during `setup.sh`, stored in Vault KV v2, and injected into Langfuse runtime via memory-backed tmpfs.

### Positive Consequences

* Application compromised in the runtime layer cannot traverse outside the `langfuse` bucket.
* Administrative commands (`Admin`) are rejected by SeaweedFS SigV4 authorization engine.
* Automated smoke tests verify that `langfuse_app` can only manipulate its own objects.

### Negative Consequences

* Requires maintaining two sets of S3 credentials in Vault KV v2.
