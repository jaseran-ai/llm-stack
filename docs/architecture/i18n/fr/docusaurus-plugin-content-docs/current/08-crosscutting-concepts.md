# 8. Concepts Transverses

Cette section décrit les patrons d'architecture universels et les concepts transverses appliqués à l'ensemble des services de la stack LLM.

---

## 8.1 Gestion des Prompts & Routage de Modèles

* **Suivi & Versioning des Prompts** : Chaque prompt exécuté via LiteLLM ou Open WebUI reçoit un ID de trace et est envoyé à Langfuse. Les modifications de prompts système, paramètres de température et compteurs de tokens sont historisés.
* **Routage de Modèles** : LiteLLM expose chaque modèle sous un alias stable (`lfm2-1.2b-rag` par défaut, servi localement par Ollama). Des modèles locaux ou distants supplémentaires peuvent être déclarés dans `litellm/custom_models.yaml` sans modifier le code client.
* **Cascades de Repli (Fallbacks)** : LiteLLM définit des cascades déclaratives. Si un fournisseur distant renvoie un code `HTTP 429 Rate Limit` ou `HTTP 500`, la requête bascule automatiquement sur le modèle alternatif suivant sans rupture de service.

---

## 8.2 Confidentialité en Vol & Garde-fous

* **Biffure à Double Moteur** :
  - **Betterleaks (Go)** : Détection ultra-rapide par motifs réguliers de milliers de signatures de clés API (AWS, GitHub, OpenAI, clés privées).
  - **Presidio Analyzer (Python)** : Modèles de reconnaissance d'entités nommées (NER) détectant les noms, adresses email, numéros de téléphone et coordonnées en anglais et en français.
* **Tokenisation Réversible Sécurisée** :
  - Les valeurs sensibles sont remplacées par des surrogate tokens déterministes.
  - La table de correspondance surrogate-vers-clair est stockée dans Redis chiffrée avec **AES-256-GCM côté client**.
  - Les clés de déchiffrement sont administrées dynamiquement via HashiCorp Vault KV v2.
* **Garde-fous des outils MCP (optionnel)** : Betterleaks expose un endpoint gRPC `ExtMcp` (`50052`) compatible avec le projet open source Agentgateway, permettant de biffer les arguments et résultats d'outils MCP lorsqu'une telle passerelle est déployée devant des serveurs MCP.

---

## 8.3 Isolation des Secrets en Mémoire Vive & Cycle de Vie

* **Ingestion Zéro Disque** :
  1. `setup.sh` génère des secrets cryptographiques aléatoires via `openssl rand -hex 32`.
  2. Les secrets sont poussés en HTTPS dans le stockage HashiCorp Vault KV v2 (`secret/data/...`).
  3. Vault Agent s'authentifie via des identifiants AppRole restreints en lecture seule.
  4. Vault Agent rend les templates Consul (`.tpl`) dans un point de montage `tmpfs` en RAM (`/vault/secrets_ram`).
  5. Les applications montent `/vault/secrets_ram/*.env:ro` en lecture seule.
  6. Les permissions sont strictement appliquées (`0700` pour le répertoire, `0600` pour les fichiers).

---

## 8.4 PKI Interne & Modèle de Confiance des Certificats

* **Deux chaînes de confiance** (générées par `traefik/scripts/certs.sh` lors du `setup.sh`) :
  - **AC interne** (`internal-ca.crt`, validité 10 ans) : signe le certificat du listener Vault (`DNS:vault`, `DNS:localhost`, `IP:127.0.0.1`) dans tous les modes TLS.
  - **Chaîne d'entrée** (`tls.crt` + `ca.crt`) : certificat de `${DOMAIN}` et `*.${DOMAIN}` servi par Traefik, signé par l'AC interne (`TLS_MODE=internal`) ou par l'AC de l'opérateur à partir d'un CSR généré (`TLS_MODE=custom`).
* **Injection dans les Magasins de Confiance** :
  - La chaîne de l'AC d'entrée (`traefik/certs/ca.crt`) est montée dans `/etc/ssl/certs/local-ca.crt:ro` ; Vault, Vault Agent et le `vault-transport` de Traefik font confiance à l'AC interne.
  - Les applications Node.js reçoivent `NODE_EXTRA_CA_CERTS: "/etc/ssl/certs/local-ca.crt"`, ajoutant l'autorité locale aux racines Mozilla sans les écraser.
  - Les flags d'insécurité globale (`NODE_TLS_REJECT_UNAUTHORIZED: "0"`, `PYTHONHTTPSVERIFY: "0"`) sont éliminés.

---

## 8.5 Graphe de Dépendance au Démarrage & Cycle de Vie

Pour éviter tout interblocage ou course critique lors de l'initialisation :
1. **Tier 1 (Bases de données)** : `postgres`, `redis`, `clickhouse`, `seaweedfs` démarrent et confirment leur état sain.
2. **Tier 2 (Secrets & Identité)** : `vault` se déverrouille (unseal), `vault-agent` rend les secrets en tmpfs, `authentik-server` démarre et applique les blueprints Tier 00.
3. **Tier 3 (Ingress & Outposts)** : Authentik applique les blueprints Tier 10 ; Traefik initialise la liaison de l'outpost Forward-Auth intégré.
4. **Tier 4 (Passerelles & Applications)** : `litellm`, `betterleaks`, `open-webui`, `langfuse` et `grafana` se lancent dès que leurs dépendances sont prêtes.
