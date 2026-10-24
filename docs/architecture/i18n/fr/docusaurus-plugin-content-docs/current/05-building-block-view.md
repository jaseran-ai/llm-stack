# 5. Vue en Blocs

La Vue en Blocs fournit une décomposition hiérarchique de la stack LLM en plans logiques et conteneurs.

---

## 5.1 Niveau 1 : Décomposition des conteneurs (Diagramme C4 Containers)

Le diagramme suivant détaille la décomposition de la stack LLM en services conteneurisés et leurs flux de données :

![Diagramme des Conteneurs](@site/docs/c4/svg/structurizr-Containers.svg)

---

## 5.2 Niveau 2 : Plans d'architecture

Les composants sont organisés en six plans fonctionnels :

### 1. Plan Périmètre & Ingress
* **`cloudflared`** : Relie le réseau privé de conteneurs au réseau edge mondial de Cloudflare par tunnels sortants.
* **`traefik`** : Proxy inverse HTTP Traefik v3. Gère le routage par labels Docker, applique les en-têtes de sécurité (`HSTS`, `nosniff`, `DENY`) et route les requêtes à travers le middleware Forward-Auth d'Authentik.

### 2. Plan Gouvernance d'Identité & Secrets
* **`authentik-server` & `authentik-worker`** : Fournisseur d'identité unifié gérant les flux d'authentification, les sessions, l'émission de tokens OAuth2/OIDC et l'outpost Forward-Auth intégré.
* **`vault`** : Serveur HashiCorp Vault exploitant un listener TLS interne sur le port `8200`, administrant les chemins secrets KV v2.
* **`vault-agent`** : Démon authentifié par AppRole pour lire les secrets de Vault et rendre les templates d'environnement en mémoire vive volatile (`/vault/secrets_ram`).

### 3. Plan Passerelle & Garde-fous
* **`litellm`** : Routeur LLM compatible OpenAI, gérant les replis de providers, le suivi de latence, les quotas budgétaires et les garde-fous Presidio.
* **`betterleaks-presidio`** : Moteur de biffure unifié en Go et Python exécutant la détection regex, l'analyse NER spaCy et la tokenisation AES-256-GCM.

### 4. Plan Applications Interactives
* **`open-webui`** : Interface web conversationnelle gérant les complétions de chat, les uploads multimodaux, l'indexation documentaire RAG et la recherche web.
* **`searxng`** : Moteur de métarecherche respectueux de la vie privée fournissant des résultats web à Open WebUI.
* **`chouse-ui`** : Client web léger pour explorer les tables ClickHouse et exécuter des requêtes analytiques SQL.

### 5. Plan Stockage & Persistance
* **`postgres`** : Base de données relationnelle PostgreSQL 18 avec initialisation multi-bases (`authentik`, `langfuse`, `chouse_ui`, ainsi que la base par défaut `postgres` utilisée par LiteLLM).
* **`clickhouse`** : Base de données colonnaire stockant les traces haute fréquence de Langfuse.
* **`seaweedfs`** : Serveur unifié master, volume et S3 assurant le stockage d'exports et de documents avec authentification AWS SigV4.
* **`qdrant`** : Base de données vectorielle gérant les embeddings et la recherche par similarité pour le RAG.
* **`redis`** : Cache en mémoire pour les files de tâches Langfuse et stockage des surrogate tokens chiffrés.
* **`ollama`** : Moteur d'inférence CPU local hébergeant le modèle par défaut (`lfm2-1.2b-rag`).

### 6. Plan Observabilité & Supervision
* **`langfuse-web` & `langfuse-worker`** : Plateforme d'observabilité LLMOps traçant les prompts, latences, consommation de tokens et évaluations.
* **`prometheus`** : Collecteur de métriques temporelles interrogeant Traefik, LiteLLM, Qdrant, cAdvisor et Node Exporter.
* **`grafana`** : Visualiseur de dashboards pré-approvisionné avec les tableaux de bord de santé globale, trafic Traefik et télémétrie LLM.
* **`vector` & `loki`** : Pipeline d'agrégation de logs collectant les flux stdout/stderr depuis le socket Docker vers le stockage Loki TSDB.
* **`gatus`** : Page de statut automatisée sondant les endpoints HTTP et alertant en cas de dégradation.
