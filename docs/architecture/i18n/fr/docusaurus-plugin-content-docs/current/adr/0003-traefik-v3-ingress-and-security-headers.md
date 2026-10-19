# ADR 0003 : Ingress Traefik v3 et Headers de Sécurité

* **Statut** : Accepté
* **Décideurs** : Mainteneurs de LLM Stack
* **Date** : 2026-08-22
* **Histoire Technique** : Standardisation de l'ingress et durcissement de la sécurité périmétrique

## Contexte et Problématique

La plateforme utilisait initialement Caddy comme proxy inverse, ce qui imposait des builds de conteneurs personnalisés avec des plugins non officiels pour les challenges ACME DNS. Caddy manquait de souplesse pour le chaînage déclaratif de middlewares et pour l'instrumentation métrique avancée. De plus, les réponses HTTP ne contenaient pas d'en-têtes de sécurité de production, exposant les utilisateurs aux attaques de type clickjacking et reniflage MIME.

## Critères de Décision

* Intégration native du provider Docker avec découverte automatique des routes via labels de conteneurs.
* Chaînage déclaratif de middlewares pour le Forward-Auth et les politiques de sécurité.
* Endpoint d'export de métriques Prometheus natif.
* Application stricte d'en-têtes de sécurité HTTP sur l'ensemble des points d'entrée.

## Options Examinées

1. **Caddy** : Configuration simple, mais maintenance lourde des plugins personnalisés et intégration rigide du forward-auth.
2. **Nginx** : Éprouvé, mais la découverte dynamique des services Docker impose des démons de rechargement ou des extensions commerciales.
3. **Traefik v3** : Découverte native par labels Docker, chaînage de middlewares de premier ordre et exporteur Prometheus officiel.

## Décision Retenue

Option choisie : **Traefik v3**, combiné avec un middleware global `security-headers@file` appliquant HSTS, X-Frame-Options, Content-Type nosniff et une politique de référent stricte.

### Conséquences Positives

* Aucun build personnalisé nécessaire ; utilisation de l'image officielle épinglée par digest multi-architecture.
* Le chaînage de middlewares applique de façon transparente le Forward-Auth Authentik et les en-têtes de sécurité dans un pipeline unique.
* L'endpoint de métriques natif sur `:8082` fournit à Prometheus les latences, débits de requêtes et codes de statut par service et par routeur.

### Conséquences Négatives

* La syntaxe des labels Traefik dans `docker-compose.yml` est verbeuse.
