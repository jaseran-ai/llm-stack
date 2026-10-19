# Configuration & Variables d'Environnement

Ce document recense l'ensemble des variables de configuration et secrets utilisés par la stack LLM.

---

## 1. Variables Globales de Plateforme

| Variable | Description | Exemple / Valeur par défaut | Obligatoire ? |
|---|---|---|---|
| `DOMAIN` | Nom de domaine de base pour le routage et les sous-domaines | `example.local` | Oui |
| `TZ` | Fuseau horaire du système pour les logs et cron | `UTC` | Oui |
| `BACKUP_PASSPHRASE` | Passphrase de chiffrement des archives GnuPG AES-256 | *(Généré aléatoirement)* | Oui |
| `TELEMETRY_ENABLED` | Désactivation explicite des balises de télémétrie tierces | `false` | Oui |

---

## 2. Gestion des Secrets (Vault KV v2)

Tous les identifiants sont générés dynamiquement dans Vault KV v2 et rendus dans `/vault/secrets_ram/*.env`.

| Fichier d'environnement | Variable | Description |
|---|---|---|
| `authentik.env` | `AUTHENTIK_SECRET_KEY` | Clé secrète de signature des sessions Authentik |
| `authentik.env` | `AUTHENTIK_POSTGRESQL__PASSWORD` | Mot de passe de la base PostgreSQL d'Authentik |
| `litellm.env` | `LITELLM_MASTER_KEY` | Clé d'administration principale de la passerelle LiteLLM |
| `litellm.env` | `LITELLM_SALT_KEY` | Sel de dérivation pour le chiffrement des tokens LiteLLM |
| `langfuse.env` | `LANGFUSE_S3_ACCESS_KEY` | Clé d'accès IAM S3 restreinte au bucket `langfuse` |
| `langfuse.env` | `LANGFUSE_S3_SECRET_KEY` | Clé secrète IAM S3 restreinte |
| `qdrant.env` | `QDRANT__SERVICE__API_KEY` | Clé API requise pour accéder à la base vectorielle Qdrant |
| `betterleaks.env` | `BETTERLEAKS_ENCRYPTION_KEY` | Clé AES 256 bits pour la tokenisation Redis chiffrée côté client |

---

## 3. Points d'Extension

Pour personnaliser la stack sans modifier le dépôt git :
* **Cibles Prometheus privées** : Déposez vos cibles dans `prometheus/targets.d/*.yml` (ignoré par git).
* **Sondes Gatus privées** : Déposez vos endpoints de monitoring dans `gatus/endpoints.d/*.yaml` (ignoré par git).
* **Modèles LLM privés** : Déclarez vos endpoints de modèles privés dans `litellm/custom_models.yaml`.
* **Surcharges Compose locales** : Déposez vos surcharges dans `docker-compose.override.yml` (ignoré par git).
