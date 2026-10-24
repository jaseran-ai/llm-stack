# Spécification de l'API Publique

Cette référence détaille les endpoints de l'API REST publique exposés par la stack LLM. Cette spécification est dérivée automatiquement de la passerelle en production et ne contient que les opérations marquées `x-llm-stack-audience: public`.

> **Spécification Machine** : [`openapi-public.json`](openapi-public.json)

---

## URL de Base Ingress

```text
https://chat.${DOMAIN}/api
https://litellm.${DOMAIN}/v1
```

Toutes les requêtes requièrent une authentification par Bearer token :
```text
Authorization: Bearer <LITELLM_MASTER_KEY>
```

---

## 1. Lister les Modèles (`GET /v1/models`)

Renvoie la liste des identifiants de modèles et alias de routage actuellement actifs.

* **Méthode** : `GET`
* **Chemin** : `/v1/models`
* **Réponse** : `HTTP 200 OK`
```json
{
  "object": "list",
  "data": [
    {
      "id": "lfm2-1.2b-rag",
      "object": "model",
      "owned_by": "llm-stack"
    }
  ]
}
```

---

## 2. Créer une Complétion de Chat (`POST /v1/chat/completions`)

Soumet un prompt pour génération avec biffure automatique des secrets et données personnelles.

* **Méthode** : `POST`
* **Chemin** : `/v1/chat/completions`
* **Charge utile** :
```json
{
  "model": "lfm2-1.2b-rag",
  "messages": [
    {"role": "user", "content": "Explique l'architecture zero-trust en un paragraphe."}
  ],
  "temperature": 0.7,
  "stream": false
}
```
* **Réponse** : `HTTP 200 OK` (Objet standard ChatCompletion OpenAI).

---

## 3. Créer des Embeddings de Texte (`POST /v1/embeddings`)

Génère un vecteur d'embedding pour l'indexation sémantique et la recherche.

* **Méthode** : `POST`
* **Chemin** : `/v1/embeddings`
* **Charge utile** :
```json
{
  "model": "text-embedding-nomic",
  "input": "Extrait de document textuel à vectoriser"
}
```
* **Réponse** : `HTTP 200 OK` (Tableau de coordonnées d'embedding en virgule flottante).

---

## 4. Sonde de Santé (`GET /healthz`)

Sonde publique de disponibilité et de vivacité pour répartiteurs de charge.

* **Méthode** : `GET`
* **Chemin** : `/healthz`
* **Réponse** : `HTTP 200 OK` (`{"status": "ok"}`).
