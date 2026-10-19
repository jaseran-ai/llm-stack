# Qdrant Vector Database - API Usage & Testing Guide

This guide provides step-by-step instructions to verify, query, and manage the **Qdrant Vector Database** instance deployed in the LLM Stack architecture.

---

## Authentication & API Key

Qdrant is secured using an API key generated dynamically during stack initialization (`./init.sh`).

To load your Qdrant API key into a shell variable:

```bash
cd llm-stack
QDRANT_KEY=$(grep QDRANT_API_KEY .env | cut -d '=' -f2)
echo "Loaded Qdrant API Key: $QDRANT_KEY"
```

---

## Quick Verification Tutorial

You can run the following `curl` commands to test the full lifecycle of vector storage and search in Qdrant.

### 1. Health Check (`/healthz`)

Check if the Qdrant service is alive and healthy:

```bash
curl -s http://127.0.0.1:6333/healthz
```

**Expected output:**
```text
healthz check passed
```

---

### 2. List Existing Collections

List all vector collections currently registered (for example, Open WebUI's knowledge base collections):

```bash
curl -s -H "api-key: $QDRANT_KEY" http://127.0.0.1:6333/collections
```

**Expected output:**
```json
{
  "result": {
    "collections": [
      { "name": "open-webui_memories" },
      { "name": "open-webui_files" },
      { "name": "open-webui_knowledge" }
    ]
  },
  "status": "ok",
  "time": 0.00001
}
```

---

### 3. Create a Test Collection

Create a new vector collection named `test_vector_collection`, configured for 4-dimensional vectors using cosine similarity:

```bash
curl -s -X PUT "http://127.0.0.1:6333/collections/test_vector_collection" \
  -H "api-key: $QDRANT_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "vectors": {
      "size": 4,
      "distance": "Cosine"
    }
  }'
```

**Expected output:**
```json
{
  "result": true,
  "status": "ok"
}
```

---

### 4. Insert Vector Points with Metadata (Payload)

Upsert a vector point into `test_vector_collection` with an attached text payload:

```bash
curl -s -X PUT "http://127.0.0.1:6333/collections/test_vector_collection/points" \
  -H "api-key: $QDRANT_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "points": [
      {
        "id": 1,
        "vector": [0.1, 0.2, 0.3, 0.4],
        "payload": {
          "text": "Hello Qdrant Vector DB!",
          "category": "smoke_test"
        }
      }
    ]
  }'
```

**Expected output:**
```json
{
  "result": {
    "operation_id": 0,
    "status": "acknowledged"
  },
  "status": "ok"
}
```

---

### 5. Run a Nearest Neighbor Vector Search

Perform a similarity search using the target vector `[0.1, 0.2, 0.3, 0.4]` to retrieve matching payload metadata:

```bash
curl -s -X POST "http://127.0.0.1:6333/collections/test_vector_collection/points/search" \
  -H "api-key: $QDRANT_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "vector": [0.1, 0.2, 0.3, 0.4],
    "limit": 1,
    "with_payload": true
  }'
```

**Expected output:**
```json
{
  "result": [
    {
      "id": 1,
      "version": 0,
      "score": 1.0,
      "payload": {
        "text": "Hello Qdrant Vector DB!",
        "category": "smoke_test"
      }
    }
  ],
  "status": "ok"
}
```

---

### 6. Delete the Test Collection

Clean up the test collection when you're done:

```bash
curl -s -X DELETE "http://127.0.0.1:6333/collections/test_vector_collection" \
  -H "api-key: $QDRANT_KEY"
```

**Expected output:**
```json
{
  "result": true,
  "status": "ok"
}
```

---

## Docker Configuration Reference

In `docker-compose.yml`, Qdrant is configured as follows:

```yaml
  qdrant:
    image: qdrant/qdrant:v1.13.4
    container_name: qdrant
    restart: unless-stopped
    ports:
      - "127.0.0.1:6333:6333"
      - "127.0.0.1:6334:6334"
    environment:
      - QDRANT__SERVICE__API_KEY=${QDRANT_API_KEY}
    volumes:
      - qdrant_data:/qdrant/storage
```

---

## Endpoints Overview

| Endpoint | Method | Auth required | Description |
| :--- | :--- | :--- | :--- |
| `http://127.0.0.1:6333/healthz` | `GET` | No | Service liveness check |
| `http://127.0.0.1:6333/collections` | `GET` | Yes (`api-key`) | List vector collections |
| `http://127.0.0.1:6333/collections/{name}` | `PUT` | Yes (`api-key`) | Create a collection |
| `http://127.0.0.1:6333/collections/{name}/points` | `PUT` | Yes (`api-key`) | Insert/upsert vector points |
| `http://127.0.0.1:6333/collections/{name}/points/search` | `POST` | Yes (`api-key`) | Run a similarity search |
| `http://127.0.0.1:6333/collections/{name}` | `DELETE` | Yes (`api-key`) | Delete a collection |
