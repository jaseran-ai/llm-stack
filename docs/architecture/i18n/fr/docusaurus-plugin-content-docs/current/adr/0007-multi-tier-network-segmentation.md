# ADR 0007 : Segmentation Réseau Multi-Tiers

* **Statut** : Accepté
* **Décideurs** : Mainteneurs de LLM Stack
* **Date** : 2026-10-18
* **Histoire Technique** : Segmentation réseau interne Docker et isolation des bases de données

## Contexte et Problématique

Auparavant, l'ensemble des conteneurs de la stack partageaient un unique réseau bridge (`llm-stack_default`). Bien que Traefik et Cloudflared ne transmettent que les flux HTTP prévus, un conteneur applicatif compromis (ex : Open WebUI ou Grafana) pouvait tenter une découverte réseau latérale ou un balayage de ports vers les bases de données internes (`postgres`, `clickhouse`, `redis`) sur le bridge Docker. De plus, une base de données compromise aurait pu exfiltrer des données vers Internet.

## Critères de Décision

* Défense en profondeur et étanchéité stricte entre les différents tiers.
* Isolation des bases relationnelles, analytiques et de cache vis-à-vis des conteneurs exposés à Internet.
* Zéro accès externe à Internet pour les bases de données (réseau `internal: true`).
* Migration sans interruption de service, sans rupture de la découverte OIDC ni des sondes de santé.
* Préservation du routage inverse Traefik et des services exposés.

## Options Examinées

1. **Réseau bridge unique (précédent)** : Simple, aucune complexité de routage, mais aucune barrière contre les mouvements latéraux.
2. **Isolation stricte par service individuel** : Trop de réseaux, complexité de maillage disproportionnée.
3. **Segmentation réseau multi-tiers** :
   - `llm-stack_default` : Réseau bridge applicatif et routage edge (`172.18.0.0/16`).
   - `internal-backend` (`name: llm-stack_backend`, `internal: true`, `172.24.0.0/16`) : Réseau backend isolé pour bases de données et caches, sans passerelle par défaut. Les bases relationnelles et caches (`postgres`, `clickhouse`, `redis`) résident exclusivement sur ce réseau. Les consommateurs applicatifs autorisés (`authentik`, `litellm`, `langfuse-web`, `langfuse-worker`, `chouse-ui`, `betterleaks`, `gatus`) sont raccordés aux deux réseaux (*dual-homed*).

## Décision Retenue

Option retenue : **Segmentation réseau multi-tiers avec backend interne dédié (`internal-backend`)**.

### Détails de Mise en Œuvre

1. **Déclaration GitOps dans Docker Compose** :
   - `networks.default` : explicitement nommé `llm-stack_default`.
   - `networks.internal-backend` : explicitement nommé `llm-stack_backend` avec `internal: true`.
2. **Isolation des Bases de Données** :
   - `postgres`, `clickhouse` et `redis` sont rattachés exclusivement à `internal-backend`.
   - L'accès Internet sortant est bloqué au niveau du noyau (`Network is unreachable`).
   - L'accès entrant depuis les conteneurs hors backend (ex : `searxng`) est bloqué au niveau de la résolution DNS et du routage IP.
3. **Épinglage du Réseau Fournisseur Traefik** :
   - Ajout de `providers.docker.network: "llm-stack_default"` dans `traefik/traefik.yml` et `traefik/traefik.yml.template` afin d'empêcher Traefik d'acheminer par erreur le trafic vers les adresses IP backend internes des conteneurs multi-réseaux.
4. **Validation Empirique Automatisée** :
   - 28/28 tests de fumée validés avec succès (`./smoke_test.sh`).
   - Blocage du trafic sortant vers Internet validé (`Network is unreachable`).
   - Isolation latérale validée (les connexions depuis un conteneur non autorisé échouent à la résolution de nom).

### Conséquences Positives

* Les bases de données résident sur un réseau sans passerelle par défaut (`internal: true`), empêchant toute exfiltration de données même en cas d'exécution de code arbitraire.
* Les mouvements latéraux depuis les conteneurs frontaux vers les bases sont physiquement bloqués par Docker.
* Le routage Traefik demeure déterministe et protégé contre les ambiguïtés multi-IP.
* Conformité avec les standards de sécurité Zero-Trust de niveau entreprise.

### Conséquences Négatives

* Les conteneurs multi-réseaux (Authentik, Langfuse, LiteLLM) doivent déclarer leur appartenance à `default` et à `internal-backend`.
* Les ports hôtes des bases de données ne sont plus publiés via `docker-proxy` sur localhost (les réseaux internes désactivent le mappage de ports hôtes), nécessitant l'exécution des tests d'administration via `docker compose exec` ou l'utilisation des IP internes.
