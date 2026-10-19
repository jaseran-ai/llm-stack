# S'authentifier via le SSO Authentik & Gérer les Rôles

Ce guide explique comment s'authentifier sur le portail central et gérer les droits d'accès basés sur les rôles.

---

## Accéder au Tableau de Bord

1. Ouvrez votre navigateur et accédez au domaine principal :
   ```text
   https://authentik.${DOMAIN}
   ```
2. Saisissez vos identifiants. Sur une installation neuve, utilisez le compte `admin` et le mot de passe généré par `./setup.sh`.
3. Une fois authentifié, le **Tableau de Bord des Applications** présente l'ensemble des services autorisés pour votre compte.

---

## Contrôle d'Accès Basé sur les Rôles (RBAC)

La plateforme applique deux groupes principaux :

### 1. Groupe `admins`
Les membres du groupe `admins` disposent d'un accès intégral aux 16 applications de la stack, comprenant :
* Les tableaux de bord d'infrastructure : Grafana, Traefik Dashboard, Dozzle, Gatus.
* Les interfaces de bases de données : CHouse UI, console SeaweedFS.
* Les consoles de gestion : HashiCorp Vault, console d'administration Authentik.

### 2. Groupe `users`
Les utilisateurs standards (ex : comptes de démonstration `alice` et `bob`) sont strictement limités :
* Application autorisée : **Open WebUI** (`chat.${DOMAIN}`).
* Tous les endpoints d'administration, de stockage ou de télémétrie renvoient un code `HTTP 403 Forbidden` ou redirigent vers la mire de connexion.

---

## Assigner un Utilisateur à un Groupe
1. Connectez-vous en tant qu'`admin` et ouvrez la console d'administration Authentik (`/if/admin/`).
2. Rendez-vous dans **Directory** → **Users**.
3. Sélectionnez l'utilisateur cible, cliquez sur **Groups**, et assignez ou retirez le groupe `admins` ou `users`.
4. Les changements sont effectifs immédiatement dès la requête HTTP suivante.
