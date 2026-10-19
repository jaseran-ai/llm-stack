# 6. Vue d'Exécution

Cette section détaille les flux d'exécution dynamiques et les séquences pour les scénarios d'exécution critiques.

---

## 6.1 Scénario 1 : Authentification utilisateur via Forward-Auth (Pattern A)

Lorsqu'un utilisateur accède à un outil administratif (ex : Open WebUI, Grafana, Dozzle), Traefik intercepte la requête et évalue l'authentification auprès d'Authentik avant de relayer en amont :

![Flux SSO Forward-Auth](@site/docs/diagrams/svg/sso-forward-auth.svg)

### Déroulement de la séquence
1. L'utilisateur sollicite `https://chat.{DOMAIN}/` via son navigateur.
2. Traefik intercepte la requête et exécute une sous-requête interne vers l'outpost intégré d'Authentik (`/outpost.goauthentik.io/auth/traefik`).
3. Si un cookie de session valide est présent et que l'utilisateur appartient au groupe autorisé (`admins` ou `users`), l'outpost répond `HTTP 200` avec les en-têtes d'identité (`X-authentik-username`, `X-authentik-email`).
4. Traefik injecte ces en-têtes vérifiés et transmet la requête au conteneur Open WebUI.
5. En l'absence d'authentification valide, l'outpost répond `HTTP 401/302`, redirigeant le navigateur vers le flux de connexion Authentik.

---

## 6.2 Scénario 2 : Complétion LLM avec biffure PII Betterleaks & Tokenisation sécurisée

Lorsqu'un client soumet une complétion de chat, le prompt est intercepté, analysé et nettoyé avant exécution, et la réponse est sécurisée :

![Flux Garde-fou LLM](@site/docs/diagrams/svg/llm-completion-guardrail.svg)

### Déroulement de la séquence
1. Le client transmet un prompt contenant des données sensibles (ex: clé API ou adresse email) à l'endpoint `/v1/chat/completions` de LiteLLM.
2. LiteLLM déclenche un hook de garde-fou pré-appel vers Betterleaks Presidio (`/v1/anonymize`).
3. Betterleaks exécute la détection regex et la classification NER spaCy.
4. Les entités sensibles détectées sont substituées par des surrogate tokens aléatoires (ex : `<SURROGATE_TOKEN_API_KEY_01>`).
5. Betterleaks chiffre la table de correspondance originale-vers-surrogate avec **AES-256-GCM côté client** à l'aide de clés gérées dans Vault, et stocke le chiffré dans Redis avec un TTL.
6. Le prompt assaini est transmis au moteur d'inférence (Ollama ou provider externe).
7. Le moteur d'inférence produit une réponse ne mentionnant que le surrogate token.
8. LiteLLM déclenche un hook post-appel vers Betterleaks (`/v1/deanonymize`).
9. Betterleaks déchiffre la correspondance depuis Redis, restaure la valeur originale pour le client légitime et diffuse le stream de réponse final.

---

## 6.3 Scénario 3 : Ingestion d'objets S3 via IAM SigV4 restreint

Lorsque Langfuse exporte des traces ou qu'Open WebUI téléverse des documents :
1. L'application lit les identifiants S3 restreints (`LANGFUSE_S3_ACCESS_KEY` / `LANGFUSE_S3_SECRET_KEY`) depuis le montage tmpfs en RAM (`/vault/secrets_ram/langfuse.env`).
2. L'application calcule les signatures d'autorisation AWS SigV4 standards restreintes strictement au bucket cible (`langfuse`).
3. SeaweedFS vérifie la signature SigV4 par rapport à l'identité IAM générée lors du `setup.sh`.
4. La requête réussit car l'identité possède explicitement les actions `Read:langfuse`, `Write:langfuse` et `List:langfuse`. Toute tentative d'accéder aux endpoints administratifs ou à d'autres buckets est rejetée avec `HTTP 403 Forbidden`.
