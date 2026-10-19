# How-To: Configure Web Search in Open WebUI

This guide explains how to enable private, grounded web search in Open WebUI using the integrated SearXNG metasearch service.

---

## Overview

The stack bundles **SearXNG**, an open-source, privacy-preserving metasearch engine. When enabled, Open WebUI queries SearXNG over internal container networking to ground conversational responses in current real-world facts.

---

## Configuration

Web search is configured declaratively in `docker-compose.yml` for Open WebUI:

```yaml
  open-webui:
    environment:
      ENABLE_RAG_WEB_SEARCH: "True"
      RAG_WEB_SEARCH_ENGINE: "searxng"
      RAG_WEB_SEARCH_RESULT_COUNT: 5
      SEARXNG_QUERY_URL: "http://searxng:8080/search?q=<query>&format=json"
```

---

## Using Web Search in Conversations

1. Open **Open WebUI** (`https://chat.${DOMAIN}`).
2. In the chat prompt input box, click the **Web Search** toggle icon (globe icon).
3. Submit your prompt (e.g., *"What were the latest AI developments this week?"*).
4. Open WebUI executes a metasearch through SearXNG, retrieves relevant snippets, indexes them temporarily in Qdrant, and synthesizes an answer with direct URL citations.
