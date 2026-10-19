# 10. Exigences de Qualité

Cette section définit l'arbre de qualité et les scénarios de qualité concrets pour la stack LLM selon la norme ISO 25010.

---

## 10.1 Arbre de Qualité

```text
Exigences de Qualité
├── 1. Sécurité & Confidentialité (Poids : Critique)
│   ├── Confidentialité : Secrets en mémoire (tmpfs 0700/0600), zéro persistance disque.
│   ├── Intégrité : Vérification TLS interne obligatoire, zéro bypass, S3 SigV4 signé.
│   ├── Authentification : Authentik source unique, Forward-Auth et RBAC OIDC.
│   └── Données privées : Biffure de secrets et PII en vol, tokenisation chiffrée AES-256-GCM.
├── 2. Reproductibilité & Portabilité (Poids : Haut)
│   ├── Configuration as Code : Reproductibilité 100% via ./setup.sh sur checkout vierge.
│   ├── Inférence CPU autonome : Ollama intégré s'exécute sans exiger de GPU NVIDIA.
│   └── Épinglage Multi-Arch : Digests SHA256 multi-arch stricts sur toutes les images.
├── 3. Fiabilité & Tolérance aux Pannes (Poids : Haut)
│   ├── Repli de Modèles (Fallbacks) : Cascade automatique sur rate limit ou erreur API.
│   ├── Supervision automatisée : Sondes GitOps Gatus et routage d'alertes Alertmanager.
│   └── Sauvegardes atomiques : pg_dumpall chiffré et archives de volumes vérifiées.
└── 4. Observabilité & Performance (Poids : Moyen)
    ├── Latence & Traces : Spans Langfuse à la microseconde et suivi des tokens consommés.
    └── Métriques système : Scraping temporel Prometheus et dashboards exécutifs Grafana.
```

---

## 10.2 Scénarios de Qualité

| Identifiant | Attribut de qualité | Stimulus / Déclencheur | Réponse d'architecture & Mesure |
|---|---|---|---|
| `QS-SEC-01` | **Confidentialité** | Un processus compromis s'exécute dans un conteneur non privilégié. | Impossible de lire les secrets des autres conteneurs : `/vault/secrets_ram` est un point de montage tmpfs isolé en mode `0700`. |
| `QS-SEC-02` | **Vie privée** | Le prompt utilisateur contient des clés d'API ou des numéros de carte bancaire. | Betterleaks Presidio intercepte le flux en < 30ms et substitue les secrets par des surrogate tokens avant transmission au LLM. |
| `QS-REL-01` | **Tolérance aux pannes** | Un fournisseur LLM cloud renvoie un code `HTTP 429 Too Many Requests`. | LiteLLM réachemine automatiquement la complétion vers le modèle de repli suivant en < 250ms sans exception client. |
| `QS-OPS-01` | **Reproductibilité** | Exécution d'un clone vierge sur un poste de développeur propre. | `./setup.sh` génère les secrets, initialise les bases de données et valide 28/28 tests smoke en moins de 5 minutes. |
