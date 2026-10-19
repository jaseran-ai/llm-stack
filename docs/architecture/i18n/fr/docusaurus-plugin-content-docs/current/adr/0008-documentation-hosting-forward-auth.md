# ADR 0008 : Hébergement et Contrôle d'Accès de la Documentation via Authentik Forward-Auth

* **Statut** : Accepté
* **Décideurs** : Mainteneurs de LLM Stack
* **Date** : 2026-10-18
* **Histoire Technique** : Publication et sécurisation unifiée SSO des documentations Utilisateur et Architecture

## Contexte et Problématique

La stack LLM maintient deux sites de documentation Docusaurus strictement séparés :
1. `docs-user` (`docs/user/`) : Guides utilisateurs, tutoriels, fiches pratiques et références selon la méthodologie Diátaxis.
2. `docs-architecture` (`docs/architecture/`) : Documentation d'architecture interne basée sur arc42, diagrammes C4 et ADR au format MADR.

Initialement, ces sites étaient construits et testés de manière isolée via Docker Compose (`docs/compose.yaml`), sans être publiés ni exposés aux utilisateurs. Le projet requiert la publication des deux sites sous un contrôle d'accès Zero-Trust :
- `docs-user` doit être accessible à tous les utilisateurs authentifiés (groupe `users`) ainsi qu'aux administrateurs (groupe `admins`).
- `docs-architecture` contient des éléments sensibles (modélisation des menaces, topologie réseau interne, choix de sécurité) et doit être strictement réservé aux administrateurs (groupe `admins`).
- Les deux sites doivent s'intégrer nativement dans le tableau de bord Authentik avec leurs icônes officielles, bénéficier des en-têtes de sécurité Traefik et des sondes de supervision GitOps Gatus.

## Critères de Décision

* Authentification unique (SSO) conforme à la gouvernance de la stack (Règle 6).
* Zéro accès non authentifié (bloquage systématique des requêtes anonymes avec redirection HTTP 302/401).
* Contrôle d'accès basé sur les rôles (RBAC) :
  * Documentation utilisateur accessible à tous les utilisateurs authentifiés (`users` + `admins`).
  * Documentation d'architecture réservée exclusivement aux administrateurs (`admins`).
* Reproductibilité sous forme de code : déclaration complète des fournisseurs, applications et liaisons de stratégies dans des blueprints YAML versionnés.
* Environnement d'exécution conteneurisé et léger avec Nginx sous Alpine Linux servant des sites statiques précompilés.
* Prise en charge stricte du bilinguisme (source en anglais + traduction en français).

## Options Examinées

1. **Hébergement public ouvert** : Non sécurisé ; fuite de la topologie opérationnelle et de la documentation d'architecture.
2. **Authentification HTTP basique (Basic Auth)** : Identifiants hors bande, pas d'audit centralisé, pas de provisionnement dynamique ni d'intégration au dashboard Authentik.
3. **Pattern A : Authentik Forward-Auth via Traefik (Option Retenue)** :
   - Traefik intercepte les requêtes HTTP entrantes sur `docs.${DOMAIN}` et `arch.${DOMAIN}`.
   - Les requêtes sont filtrées par le middleware forward-auth d'Authentik avant d'atteindre les serveurs web de documentation.
   - Authentik applique les liaisons déclaratives de stratégies RBAC :
     * `docs-user` autorise les groupes `admins` et `users`.
     * `docs-architecture` autorise exclusivement le groupe `admins`.
   - Les contenus statiques sont servis par des conteneurs Alpine Nginx (`llm-stack-docs-user` et `llm-stack-docs-architecture`) consommant moins de 128 Mo de RAM chacun.

## Décision Retenue

Option retenue : **Pattern A : Authentik Forward-Auth via Traefik avec Blueprints YAML Déclaratifs**.

### Détails de Mise en Œuvre

1. **Services Docker Compose** :
   - `docs-user` : compile/exécute `llm-stack-docs-user`, port `8080`, mappé localement sur `127.0.0.1:8085`, limite mémoire 128 Mo.
   - `docs-architecture` : compile/exécute `llm-stack-docs-architecture`, port `8080`, mappé localement sur `127.0.0.1:8086`, limite mémoire 128 Mo.
   - Healthcheck configuré avec `wget -q -O - http://127.0.0.1:8080/ || exit 1`.
2. **Blueprints Déclaratifs Authentik (`authentik/blueprints/10-forward-auth.yaml`)** :
   - Déclaration des ProxyProviders `docs-forward-auth` et `arch-forward-auth` en mode `forward_single`.
   - Création des applications `docs` et `arch` avec icône CDN officielle (`https://cdn.jsdelivr.net/gh/selfhst/icons/png/docusaurus.png`).
   - Attachement des liaisons de stratégie (*Policy Bindings*) :
     * `docs` : groupes `admins` (ordre 0) et `users` (ordre 1).
     * `arch` : groupe `admins` (ordre 0).
   - Liaison des deux fournisseurs au composant `authentik Embedded Outpost`.
3. **Routage Traefik et En-têtes de Sécurité** :
   - Configuration des labels Traefik associant le middleware `authentik@docker` et les en-têtes de sécurité stricts (HSTS, nosniff, SAMEORIGIN).
4. **IaC Cloudflare Zero Trust** :
   - Ajout des sous-domaines `"docs"` et `"arch"` dans `cloudflare/variables.tf`.
   - Application Terraform pour provisionner les enregistrements CNAME publics et les règles d'ingress du tunnel Cloudflare.
5. **Supervision GitOps Gatus** :
   - Ajout des sondes HTTP automatisées pour les deux sites de documentation dans `gatus/config.yaml.template`.
6. **Validation Empirique Automatisée (`smoke_test.py`)** :
   - Ajout de `test_docs_user` et `test_docs_arch` vérifiant le blocage anonyme, l'application des règles RBAC (Alice autorisée sur la doc utilisateur, Alice bloquée sur la doc architecture, Admin autorisé sur les deux) et la réponse HTTP 200 sur les endpoints EN et FR.

### Conséquences Positives

* Expérience SSO unifiée : les utilisateurs s'authentifient une seule fois via Authentik et accèdent aux documentations autorisées.
* La documentation d'architecture est hermétiquement protégée contre tout accès anonyme ou non administrateur.
* Les deux sites apparaissent sous forme de tuiles interactives sur le tableau de bord central Authentik (`https://home.${DOMAIN}/`).
* Déploiement 100 % reproductible via `./setup.sh` et les blueprints GitOps.

### Conséquences Négatives

* L'accès à la documentation requiert une connectivité réseau active pour joindre l'IdP Authentik lors de la phase d'autorisation initiale.
