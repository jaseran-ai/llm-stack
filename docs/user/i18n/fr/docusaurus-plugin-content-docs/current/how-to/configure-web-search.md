# Configurer la Recherche Web dans Open WebUI

Ce guide explique comment activer la recherche web privée dans Open WebUI à l'aide du métamoteur SearXNG intégré.

---

## Vue d'ensemble

La stack intègre **SearXNG**, un métamoteur open source respectueux de la vie privée. Lorsqu'il est activé, Open WebUI interroge SearXNG via le réseau interne pour ancrer ses réponses dans des informations factuelles récentes.

---

## Configuration

La recherche web est configurée de façon déclarative dans `docker-compose.yml` pour Open WebUI :

```yaml
  open-webui:
    environment:
      ENABLE_RAG_WEB_SEARCH: "True"
      RAG_WEB_SEARCH_ENGINE: "searxng"
      RAG_WEB_SEARCH_RESULT_COUNT: 5
      SEARXNG_QUERY_URL: "http://searxng:8080/search?q=<query>&format=json"
```

---

## Utiliser la Recherche Web dans le Chat

1. Ouvrez **Open WebUI** (`https://chat.${DOMAIN}`).
2. Dans la zone de saisie du prompt, cliquez sur l'icône de globe **Recherche Web**.
3. Saisissez votre question (ex: *"Quelles sont les dernières annonces en intelligence artificielle cette semaine ?"*).
4. Open WebUI lance une métarecherche via SearXNG, extrait les résumés pertinents, les indexe temporairement dans Qdrant et synthétise une réponse accompagnée des sources citées.
