# 4. Stratégie de Solution

Cette section résume les stratégies d'architecture fondamentales et les choix technologiques structurant la stack LLM.

---

## 4.1 Stratégies d'architecture fondamentales

1. **Défense en profondeur stratifiée** :
   La sécurité ne repose pas sur un composant unique. La protection périmétrique (Tunnel Cloudflare, en-têtes Traefik) est doublée par une vérification d'identité obligatoire (Authentik Forward-Auth et OIDC natif), des listeners TLS internes (Vault), l'isolation des secrets en mémoire (`tmpfs`) et la biffure des PII en temps réel (Betterleaks).

2. **Tout en déclaratif (CaC)** :
   Chaque paramètre est déclaratif :
   * **Infrastructure** : Docker Compose (`docker-compose.yml`) + Terraform Cloudflare (`cloudflare/`).
   * **Identité & Accès** : Blueprints Authentik YAML (`authentik/blueprints/`).
   * **Observabilité** : Règles d'alertes Prometheus (`prometheus/rules/`), sources Grafana et sondes Gatus (`gatus/config.yaml`).
   * **Routage de modèles** : Configuration LiteLLM (`litellm/litellm-config.yaml`).

3. **Plan de secrets en mémoire vive prioritaire** :
   Le stockage physique non-volatil est considéré comme non fiable pour les secrets. Tous les identifiants, tokens et clés de chiffrement générés sont injectés dans HashiCorp Vault KV v2 et rendus par Vault Agent sur un point de montage `tmpfs` en RAM (`/vault/secrets_ram`). Les secrets s'effacent lors de l'arrêt électrique.

4. **Tokenisation Zero-Trust & Confidentialité** :
   Plutôt qu'un masquage irréversible (`[REDACTED]`), la plateforme implémente une tokenisation réversible sécurisée. Les données sensibles sont substituées par des surrogate tokens aléatoires, tandis que la table de correspondance est conservée dans Redis chiffrée en AES-256-GCM.

5. **Ingestion & Inférence locales et autonomes** :
   La stack fournit une inférence locale sans dépendance externe via Ollama (`lfm2.5-thinking:1.2b`), un stockage objet S3 local via SeaweedFS et une indexation vectorielle locale avec Qdrant.

---

## 4.2 Décisions relatives à la stack technologique

| Domaine technologique | Technologie retenue | Justification stratégique |
|---|---|---|
| **Proxy inverse** | **Traefik v3** | Routage dynamique par labels Docker, chaînage de middlewares et métriques Prometheus natives. |
| **Fournisseur d'identité** | **Authentik** | Modèle d'authentification double (Forward-Auth + OIDC), blueprints déclaratifs, dashboard intégré. |
| **Moteur de secrets** | **HashiCorp Vault 2.2** | Moteur KV v2, authentification AppRole, rendu automatisé de templates en mémoire vive (tmpfs). |
| **Passerelle LLM** | **LiteLLM v1.105** | Interface compatible OpenAI sur plus de 100 providers, fallbacks et suivi budgétaire. |
| **Garde-fous** | **Betterleaks + Presidio** | Détection de secrets haute cadence, reconnaissance d'entités PII bilingue, tokenisation réversible AES. |
| **Base vectorielle** | **Qdrant v1.19** | Indexation vectorielle HNSW en Rust, empreinte mémoire maîtrisée (limite 512 Mo). |
| **Stockage objet** | **SeaweedFS 4.48** | Stockage S3 ultra-rapide sous licence Apache 2.0 avec AWS SigV4 et politiques IAM granulaires. |
| **Base relationnelle** | **PostgreSQL 18.6** | Isolation multi-bases robuste pour Authentik, LiteLLM, Langfuse et CHouse UI. |
| **Base analytique** | **ClickHouse 26.7** | Base colonnaire à très haut débit pour l'ingestion massive de traces Langfuse. |
| **Observabilité** | **Prometheus + Loki + Grafana** | Métriques unifiées, flux de logs et tableaux de bord GitOps interactifs. |
