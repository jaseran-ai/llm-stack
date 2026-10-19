# Tutoriel : Ajouter une Nouvelle Application à la Stack

Ce tutoriel détaille la procédure standard en 7 étapes pour ajouter un nouveau service conteneurisé à la stack LLM.

---

## Étape 1 : Audit de Version & Épinglage de Registre
Identifiez le tag de version stable exact ou le digest SHA256 depuis le registre officiel (Docker Hub ou GitHub Container Registry). Ne jamais utiliser `:latest`.

---

## Étape 2 : Modèle d'Architecture & d'Authentification
Déterminez si l'application supporte le **Pattern A** (Forward-Auth) ou le **Pattern B** (OIDC Natif) :
* Choisissez le **Pattern A** si le service ne dispose pas de support OIDC natif. Traefik appliquera le middleware d'authentification avant de router la requête.
* Choisissez le **Pattern B** si le service sait négocier directement un code d'autorisation OpenID Connect.

---

## Étape 3 : Déclaration du Service dans Docker Compose
Ajoutez la définition du conteneur dans `docker-compose.yml` :
```yaml
  my-app:
    image: vendor/my-app:1.2.3@sha256:abcdef...
    container_name: my-app
    restart: unless-stopped
    networks:
      - llm-stack-network
    environment:
      MY_APP_SECRET: ${MY_APP_SECRET}
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.my-app.rule=Host(`my-app.${DOMAIN}`)"
      - "traefik.http.routers.my-app.entrypoints=websecure"
      - "traefik.http.routers.my-app.tls=true"
      - "traefik.http.routers.my-app.middlewares=security-headers@file,authentik-auth@file"
```

---

## Étape 4 : Déclaration des Secrets dans Vault
1. Déclarez le secret dans `.env.example`.
2. Mettez à jour `vault/scripts/provision.py` pour injecter `MY_APP_SECRET` dans Vault KV v2.
3. Configurez `vault/agent-config.hcl` et `vault/templates/my-app.env.tpl` pour que Vault Agent écrive le secret dans le volume tmpfs en RAM.

---

## Étape 5 : Intégration SSO Authentik
Créez un blueprint YAML déclaratif dans `authentik/blueprints/` :
* Définissez le Provider (Proxy Provider pour le Pattern A, OAuth2 Provider pour le Pattern B).
* Définissez l'Application avec une icône de tuile issue d'un CDN vérifié (`https://cdn.jsdelivr.net/gh/selfhst/icons/png/<name>.png`).
* Associez des politiques d'accès limitant l'application au groupe `admins` ou `users`.

---

## Étape 6 : Sonde de Santé GitOps dans Gatus
Ajoutez une sonde de santé dans `gatus/config.yaml.template` :
```yaml
  - name: my-app
    group: applications
    url: "https://my-app.${DOMAIN}/healthz"
    interval: 60s
    conditions:
      - "[STATUS] == 200"
```

---

## Étape 7 : Validation Empirique
1. Exécutez `./setup.sh` pour propager les configurations et démarrer le conteneur.
2. Ajoutez un test automatisé dans `scripts/smoke_test.py` vérifiant la réponse HTTP 200 et l'application du RBAC.
3. Validez l'ensemble :
   ```bash
   ./smoke_test.sh
   make lint
   ```
