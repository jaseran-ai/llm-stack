# Modèles Supportés & Paramètres

Ce document détaille le modèle CPU local fourni par défaut et les fournisseurs externes supportés par LiteLLM.

---

## 1. Modèle CPU Local Intégré

La stack intègre un backend d'inférence local via le conteneur `ollama`.

* **Nom du modèle** : `lfm2-1.2b-rag`
* **Alias de routage** : `lfm2-1.2b-rag`
* **Paramètres** : 1,2 milliard de paramètres
* **Quantification** : Format GGUF Q4_K_M
* **Exigences matérielles** : S'exécute intégralement sur CPU hôte (~1,8 Go de RAM consommée). Zéro GPU requis.
* **Usage prévu** : Raisonnement rapide, explications d'état, catégorisation de prompts, développement local.

---

## 2. Modèle d'Embedding de Texte

* **Nom du modèle** : `nomic-embed-text`
* **Dimensions** : 768
* **Fenêtre de contexte** : 8192 tokens
* **Usage prévu** : Vectorisation documentaire pour la recherche RAG dans Qdrant.

---

## 3. Fournisseurs Externes Supportés

LiteLLM relaie les requêtes vers plus de 100 fournisseurs cloud lorsque les clés API correspondantes sont configurées :

| Fournisseur | Modèles supportés | Clé de configuration |
|---|---|---|
| **Anthropic** | Claude 3.5 Sonnet, Claude 3.5 Haiku, Claude 3 Opus | `ANTHROPIC_API_KEY` |
| **OpenAI** | GPT-4o, GPT-4o-mini, o1-preview, o1-mini | `OPENAI_API_KEY` |
| **Google** | Gemini 1.5 Pro, Gemini 1.5 Flash | `GEMINI_API_KEY` |
| **Mistral AI** | Mistral Large 2, Mistral NeMo, Codestral | `MISTRAL_API_KEY` |
| **DeepSeek** | DeepSeek-V3, DeepSeek-R1 | `DEEPSEEK_API_KEY` |

---

## 4. Paramètres d'Inférence Standards

| Paramètre | Type | Valeur par défaut | Description |
|---|---|---|---|
| `temperature` | float | `0.7` | Aléatoire de la génération (0.0 = déterministe, 1.0 = créatif). |
| `top_p` | float | `0.9` | Seuil de troncature d'échantillonnage nucleus. |
| `max_tokens` | integer | `4096` | Limite maximale de tokens de la complétion produite. |
| `stream` | boolean | `false` | Active le streaming Server-Sent Events (SSE) pour les tokens en temps réel. |
