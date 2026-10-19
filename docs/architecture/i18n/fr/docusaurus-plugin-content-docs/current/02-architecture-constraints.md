# 2. Contraintes d'Architecture

Cette section documente les contraintes techniques, organisationnelles et réglementaires régissant le développement et le déploiement de la stack LLM.

---

## 2.1 Contraintes techniques

* **Conteneurisation sur nœud unique** : L'architecture est conçue pour s'exécuter de façon autonome au sein de Docker Compose sur une unique machine Linux. Le clustering multi-nœuds Kubernetes est hors périmètre afin de préserver la portabilité homelab et edge.
* **Fonctionnement CPU prioritaire out-of-the-box** : Bien que le passthrough GPU (`nvidia-container-toolkit`) soit supporté pour l'accélération, la configuration de base par défaut doit fonctionner de façon fiable sur CPU standard x86_64 / arm64 avec des poids GGUF quantifiés.
* **Configuration-as-Code (CaC) 100% déclarative** : Toutes les configurations doivent résider dans des templates versionnés, des blueprints déclaratifs ou des fichiers Terraform. Les modifications manuelles dans les consoles web sont strictement interdites (Règle 2).
* **Zéro secret codé en dur & Zéro valeur par défaut de repli** : Les secrets doivent être générés dynamiquement au démarrage dans HashiCorp Vault KV v2 et rendus en mémoire vive (`tmpfs`). Les syntaxes de type `${SECRET:-default}` sont formellement bannies des définitions Compose.
* **Épinglage de registre & Immuabilité des digests** : Les images de conteneurs doivent être épinglées par des digests SHA256 immuables ou des tags de version sémantiques exacts. L'utilisation de `:latest` est interdite (Règle 7).

---

## 2.2 Contraintes organisationnelles & Gouvernance

* **Standard strict de langue anglaise** : La documentation publique, les commentaires de code, les messages de commit et les sorties de scripts doivent être rédigés en anglais (validé en CI via `make no-french`).
* **Consultation préalable & Protocole CAB** : Aucun changement unilatéral d'architecture, de réseau, de schéma de base de données ou de sécurité ne peut être apporté sans présenter un diagnostic et un plan de rollback, et sans validation explicite (Règle 1).
* **Zéro indisponibilité pour le proxy principal (`litellm`)** : La passerelle de routage LLM centrale ne doit jamais être redémarrée, recréée ou interrompue sans autorisation explicite.
* **Validation empirique automatisée** : Une tâche n'est jamais terminée sur de simples hypothèses ; la preuve formelle par codes HTTP 200, logs propres et 100% de tests smoke validés (`./smoke_test.sh`) est obligatoire (Règle 3).

---

## 2.3 Conventions

* **Format de commits** : Spécification Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`, `refactor:`).
* **Méthodologies documentaires** :
  - Guides utilisateur et intégrateurs : **Méthode Diátaxis** (`docs/user/`).
  - Documentation d'architecture et ingénierie : **arc42 + C4 + MADR** (`docs/architecture/`).
