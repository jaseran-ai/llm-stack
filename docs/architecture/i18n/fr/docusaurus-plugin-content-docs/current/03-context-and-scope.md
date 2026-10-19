# 3. Contexte et Périmètre

Cette section définit les frontières externes de la stack LLM, illustrant les interactions avec les utilisateurs externes, les réseaux cloud et les fournisseurs d'IA distants.

---

## 3.1 Contexte métier

La stack LLM fonctionne comme une passerelle cognitive autonome et une plateforme auto-hébergée :
* **Trafic entrant** : Les clients et ingénieurs accèdent aux interfaces de conversation, aux tableaux de bord et aux APIs.
* **Trafic sortant** : Si configurée, la plateforme sollicite des fournisseurs LLM externes (Anthropic, OpenAI, Hugging Face) via le proxy LiteLLM, tout en conservant des capacités d'exécution locales avec Ollama.
* **Périmètre d'entrée** : Les requêtes entrantes sont acheminées par le tunnel Cloudflare Zero Trust, éliminant tout besoin d'exposer les ports 80/443 sur le routeur hôte.

---

## 3.2 Contexte technique du système (Diagramme C4 Context)

Le diagramme suivant illustre la frontière entre les utilisateurs, la stack LLM et les réseaux externes :

![System Context](@site/docs/c4/svg/structurizr-SystemContext.svg)

---

## 3.3 Matrice des interfaces externes

| Canal / Interface | Direction | Protocole | Mécanisme de sécurité | Description |
|---|---|---|---|---|
| **Cloudflare Edge** | Entrant | HTTPS (TLS 1.2+) | DNS CAA + DMARC, edge proxy | Point d'accès externe pour les utilisateurs et webhooks. |
| **Tunnel Cloudflared** | Sortant | QUIC / HTTPS chiffré | Jeton Cloudflare Zero Trust | Établit la connexion sécurisée vers l'edge Cloudflare sans redirection de port. |
| **Proxy inverse Traefik** | Entrant | HTTP / HTTPS (SAN local) | Middleware Forward-Auth, Headers de sécurité | Routage du trafic interne, terminaison TLS et vérification SSO. |
| **Authentik OIDC / SAML** | Entrant / Interne | HTTPS / JSON | Code d'autorisation OAuth2, PKCE | Authentification centralisée et émission de tokens selon les rôles. |
| **APIs LLM externes** | Sortant | HTTPS (TLS 1.3) | Clés API restreintes, proxy LiteLLM | Connexion optionnelle aux backends d'inférence cloud (ex: OpenAI, Anthropic). |
