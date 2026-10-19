# Installation et Premier Démarrage

Suivez ces instructions pour déployer une stack LLM pleinement opérationnelle sur votre machine.

---

## Prérequis {#prerequisites}

Avant de débuter, vérifiez que votre environnement respecte les exigences minimales :
* **Système d'exploitation** : Linux (Ubuntu 22.04+, Debian 12+, Fedora ou équivalent).
* **Matériel** :
  * Recommandé minimum : 4 cœurs CPU, 16 Go de RAM, 30 Go d'espace disque disponible.
  * Recommandé pour inférence locale intensive : 8+ cœurs CPU, 32 Go de RAM, ou GPU NVIDIA avec `nvidia-container-toolkit`.
* **Logiciels** :
  * **Docker Engine** (version 24.0 ou plus récente).
  * **Docker Compose** (v2.20 ou plus récente).
  * **OpenSSL** (pour la génération dynamique des secrets).

---

## Installation

La plateforme est déployée intégralement via le script d'initialisation automatisé :

1. Clonez le dépôt et placez-vous dans le répertoire :
   ```bash
   git clone https://github.com/jaseran-ai/llm-stack.git
   cd llm-stack
   ```

2. Exécutez le script d'installation :
   ```bash
   ./setup.sh
   ```

   `setup.sh` réalise automatiquement les opérations suivantes :
   * Génération de mots de passe et clés aléatoires cryptographiquement sûrs via `openssl rand -hex 32`.
   * Provisioning du stockage HashiCorp Vault KV v2 et configuration de l'authentification AppRole.
   * Génération d'une autorité de certification interne valable 10 ans et du certificat TLS SAN.
   * Rendu des fichiers d'environnement dans un volume `tmpfs` en mémoire vive (`/vault/secrets_ram`).
   * Démarrage de tous les conteneurs dans l'ordre strict de leurs dépendances.

3. Vérifiez la santé de la stack :
   ```bash
   ./smoke_test.sh
   ```
   L'ensemble des 28 suites de tests automatisées doit afficher `[OK]`.

---

## Première Connexion {#first-login}

Une fois la stack opérationnelle, accédez au portail central d'applications :
* **URL** : `https://authentik.${DOMAIN}` (ou `http://localhost:9000` en local).
* **Identifiant** : `admin`
* **Mot de passe** : Généré dynamiquement lors du `./setup.sh` et affiché à la fin de l'installation.

Depuis le tableau de bord Authentik, vous pouvez ouvrir :
* **Open WebUI** : Chat interactif et bases de connaissances RAG.
* **Grafana** : Tableaux de bord de métriques conteneurs et santé système.
* **Langfuse** : Traces d'exécution des prompts et graphiques LLMOps.
* **Dozzle** : Visualiseur de logs des conteneurs en direct.
