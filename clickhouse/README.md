# ClickHouse - Analytical Database & Query Guide

ClickHouse is the analytical storage backend for **Langfuse** (LLM traces, observations,
scores), exposed through **CHouse UI** (`https://clickhouse.${DOMAIN}`), protected by Authentik
SSO (OIDC, `group:admins` only).

---

## Files

The `clickhouse` service itself has **no configuration file** mounted — it is configured
entirely through environment variables in
[`../docker-compose.yml`](../docker-compose.yml)
(`CLICKHOUSE_DB`, `CLICKHOUSE_USER`, `CLICKHOUSE_PASSWORD`). This folder only contains this
documentation.

---

## Access

| Access point | URL / endpoint | Auth |
| :--- | :--- | :--- |
| **CHouse UI (web console)** | `https://clickhouse.${DOMAIN}` | Authentik SSO (OIDC) |
| **HTTP interface (internal)** | `http://clickhouse:8123` (Docker network only) | Basic Auth (`clickhouse` / `CLICKHOUSE_PASSWORD`) |
| **Native protocol (internal)** | `clickhouse:9000` | Same credentials |

---

## Important: There Is No Dedicated `langfuse` Database

Langfuse does **not** create a separate `langfuse` database in ClickHouse — its entire schema
lives inside the **`default`** database (see `CLICKHOUSE_DB: default` in `docker-compose.yml`).
To browse Langfuse's data in CHouse UI, expand the `default` database in the explorer, not a
database named `langfuse`.

### Tables in `default`

| Table | Engine | Content |
| :--- | :--- | :--- |
| `traces` | ReplacingMergeTree | LLM call traces (one row per top-level request) |
| `observations` | ReplacingMergeTree | Spans within a trace (latency, tokens, cost, model) |
| `scores` | ReplacingMergeTree | Evaluation scores (manual or automated) |
| `dataset_run_items` / `dataset_run_items_rmt` | ReplacingMergeTree | Dataset test run results |
| `event_log` | MergeTree | Raw ingestion event log |
| `blob_storage_file_log` | ReplacingMergeTree | References to files stored on S3 (SeaweedFS) |
| `project_environments` | AggregatingMergeTree | Per-project environment aggregation |
| `schema_migrations` | MergeTree | Langfuse schema migration tracking |
| `analytics_traces` / `analytics_observations` / `analytics_scores` | View | Aggregated views powering the Langfuse dashboard |

---

## CHouse UI Connection Seeding Gotcha

`./setup.sh` seeds the default ClickHouse connection and RBAC access policy into CHouse
UI's own SQLite database (the `chouse_ui_data` volume) via `clickhouse/provision.sh`. This step is **not automatic** if
containers are recreated with a plain `docker compose up -d` outside the full `./setup.sh` flow —
if CHouse UI shows no ClickHouse connection or no databases, re-run `clickhouse/provision.sh` manually (see
[`../setup.sh`](../setup.sh) and [`provision.sh`](provision.sh)).

---

## Example Queries (Langfuse Schema)

All queries below have been tested against real, live-ingested data (LiteLLM to Langfuse
tracing). Paste them directly into the CHouse UI **Query Editor**.

### 1. Total number of traces
```sql
SELECT count() AS nb_traces FROM default.traces
```

### 2. Most recent traces (last 10)
```sql
SELECT name, project_id, timestamp, user_id, session_id
FROM default.traces
ORDER BY timestamp DESC
LIMIT 10
```

### 3. Usage per model (call count, total cost, average latency)
```sql
SELECT
    provided_model_name,
    count() AS nb_calls,
    sum(total_cost) AS total_cost,
    avg(dateDiff('millisecond', start_time, end_time)) AS avg_latency_ms
FROM default.observations
WHERE type = 'GENERATION'
GROUP BY provided_model_name
ORDER BY nb_calls DESC
```

### 4. Total cost per day
```sql
SELECT toDate(start_time) AS day, sum(total_cost) AS cost_usd
FROM default.observations
WHERE type = 'GENERATION'
GROUP BY day
ORDER BY day DESC
```

### 5. Total tokens consumed (input/output)
```sql
SELECT
    sum(usage_details['input']) AS tokens_input,
    sum(usage_details['output']) AS tokens_output
FROM default.observations
```

### 6. Average evaluation score per score name
```sql
SELECT name, avg(value) AS avg_score, count() AS nb
FROM default.scores
GROUP BY name
```

### 7. Full detail of the latest trace (prompt input/output)
```sql
SELECT id, name, input, output, timestamp
FROM default.traces
ORDER BY timestamp DESC
LIMIT 1
```

### 8. Slowest observations (top 5 by latency)
```sql
SELECT
    name,
    provided_model_name,
    dateDiff('millisecond', start_time, end_time) AS latency_ms,
    start_time
FROM default.observations
WHERE type = 'GENERATION'
ORDER BY latency_ms DESC
LIMIT 5
```

### 9. Join traces with their observations
```sql
SELECT
    t.name AS trace_name,
    o.name AS observation_name,
    o.provided_model_name,
    o.total_cost,
    t.timestamp
FROM default.traces AS t
INNER JOIN default.observations AS o ON o.trace_id = t.id
ORDER BY t.timestamp DESC
LIMIT 20
```

### 10. All observations for a given session
```sql
SELECT o.name, o.provided_model_name, o.total_cost, o.start_time
FROM default.observations AS o
INNER JOIN default.traces AS t ON t.id = o.trace_id
WHERE t.session_id = 'YOUR_SESSION_ID'
ORDER BY o.start_time
```

---

## Accessing the CHouse UI REST API Directly (Advanced / Scripting)

CHouse UI blocks direct browser/API navigation on most endpoints (CSRF protection) unless the
`X-Requested-With: XMLHttpRequest` header is present, along with a valid
`Authorization: Bearer <accessToken>` obtained through the SSO login flow
(`POST /api/rbac/auth/sso/callback`). See
[`../smoke_test.sh`](../smoke_test.sh) (`test_chouse_ui`) for a working reference
implementation of the full SSO handshake.
