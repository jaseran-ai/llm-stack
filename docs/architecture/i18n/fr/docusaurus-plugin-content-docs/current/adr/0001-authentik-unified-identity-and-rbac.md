# ADR 0001 : Identité Unifiée et RBAC Authentik

* **Statut** : Accepté
* **Décideurs** : Mainteneurs de LLM Stack
* **Date** : 2026-08-15
* **Histoire Technique** : Migration d'Authelia et Homarr vers un IdP unifié avec blueprints déclaratifs

## Contexte et Problématique

La plateforme maintenait auparavant des solutions d'identité fragmentées : Authelia pour l'authentification proxy inverse, Homarr pour le portail d'applications, et des comptes manuels pour divers services. Cette situation entraînait des duplications de configuration, l'absence de fournisseur OIDC natif et des désynchronisations entre visibilité sur le tableau de bord et droits d'accès réels.

## Critères de Décision

* Source unique de vérité pour l'identité, les groupes et l'authentification sur tous les services.
* Support du Forward-Auth en proxy inverse (Pattern A) et d'OpenID Connect natif (Pattern B).
* Provisioning 100% déclaratif via blueprints versionnés (zéro configuration manuelle par GUI).
* Contrôle d'accès basé sur les rôles multi-tenant avec privilèges distincts pour `admins` et `users`.

## Options Examinées

1. **Authelia + Homarr** : Léger, mais sans fournisseur OIDC natif ni permissions déclaratives par application sur le dashboard.
2. **Keycloak** : Exhaustif, mais empreinte mémoire Java/JVM incompatible avec l'exécution légère sur une seule machine.
3. **Authentik** : IdP modulaire en Python/Go avec OIDC natif, outpost Forward-Auth, portail d'applications intégré et blueprints déclaratifs en YAML.

## Décision Retenue

Option choisie : **Authentik**, car il regroupe nativement la gestion d'identité, le Forward-Auth, les capacités de fournisseur OIDC et le portail applicatif en un seul moteur déclaratif.

### Conséquences Positives

* L'IdP unique élimine la synchronisation des utilisateurs et mots de passe entre plusieurs moteurs d'authentification.
* L'OIDC natif permet des flux OAuth2 sécurisés pour LiteLLM, Langfuse, CHouse UI et HashiCorp Vault.
* L'outpost Forward-Auth protège les interfaces web sans OIDC natif (Grafana, Dozzle, Qdrant, SearXNG, SeaweedFS Console).
* Le tableau de bord d'applications natif remplace Homarr, économisant les ressources d'un conteneur entier.

### Conséquences Négatives

* Empreinte mémoire supérieure à Authelia (requiert une file de tâches Redis et une base PostgreSQL).
* Nécessite un ordonnancement strict des blueprints pour éliminer les deadlocks transactionnels Celery (résolu par la hiérarchie en 3 tiers).
