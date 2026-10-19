# Inspecter les Prompts et les Traces d'Exécution dans Langfuse

Ce guide explique comment utiliser Langfuse pour tracer le cycle de vie des prompts, mesurer la latence et suivre les coûts en tokens par modèle.

---

## Accéder à Langfuse

1. Ouvrez l'interface web de Langfuse :
   ```text
   https://langfuse.${DOMAIN}
   ```
2. Cliquez sur **Se connecter avec Authentik (SSO)**.
3. Authentifiez-vous avec vos identifiants administrateur. Votre compte est automatiquement rattaché au projet par défaut (`llm-stack-project`).

---

## Explorer les Traces

* **Tableau de Bord des Traces** : Affiche chaque requête traitée par LiteLLM ou Open WebUI, avec le prompt initial, la complétion générée, la latence en millisecondes et le nombre de tokens.
* **Graphes en Cascade (Spans Waterfall)** : Décompose le temps passé entre le prétraitement du prompt, la recherche vectorielle (RAG), la biffure PII (Betterleaks) et l'inférence brute du modèle.
* **Suivi des Coûts par Modèle** : Propose des graphiques agrégeant la consommation de tokens et l'estimation des coûts par tier de modèle.
* **Scores et Évaluations** : Permet l'évaluation automatisée ou humaine des réponses générées pour mesurer leur qualité et leur fidélité factuelle.
