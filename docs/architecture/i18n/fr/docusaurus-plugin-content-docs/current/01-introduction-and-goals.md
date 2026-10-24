# 1. Introduction et Objectifs

Ce document décrit l'architecture logicielle de la **stack LLM**, une plateforme d'entreprise auto-hébergée assurant le service unifié, la gouvernance, l'observabilité et la sécurité des modèles de langage (LLM).

---

## 1.1 Vue d'ensemble des exigences

La stack LLM répond à trois exigences fonctionnelles fondamentales :
1. **Chat interactif & Recherche de connaissances (RAG)** : Une interface utilisateur riche (Open WebUI) permettant aux utilisateurs finaux de dialoguer avec des LLMs, d'indexer des documents pour la recherche sémantique (Qdrant) et d'effectuer des recherches web privées en temps réel (SearXNG).
2. **Passerelle de modèles unifiée & Garde-fous** : Une passerelle compatible OpenAI (LiteLLM) offrant clés virtuelles, budgets et replis, associée à la biffure bidirectionnelle de secrets et PII (Betterleaks + Presidio).
3. **Observabilité LLMOps complète** : Traçabilité intégrale du cycle de vie des prompts, latence, coûts en tokens et scores d'évaluation (Langfuse), couplée aux métriques globales du cluster (Prometheus), aux logs en temps réel (Loki) et aux sondes de santé déclaratives (Gatus).

---

## 1.2 Objectifs de qualité

| Priorité | Objectif | Description |
|---|---|---|
| **1** | **Reproductibilité déterministe** | L'ensemble de la plateforme peut être déployé depuis un clone vierge en une seule étape automatisée (`./setup.sh`), sans manipulation manuelle de GUI ni modifications non commitées en base de données. |
| **2** | **Sécurité Zero-Trust par défaut** | Isolation stricte du périmètre, aucun port de base de données exposé en clair, isolation des secrets en mémoire vive (Vault tmpfs) et SSO/RBAC obligatoire sur tous les endpoints. |
| **3** | **Portabilité & Efficacité des ressources** | Inférence locale CPU clé en main (`lfm2-1.2b-rag`) garantissant l'exécution autonome de la stack sur un ordinateur portable, une machine virtuelle ou un serveur homelab sans exiger de GPU. |
| **4** | **Vérifiabilité empirique** | Chaque fonctionnalité, frontière de sécurité et contrainte RBAC est automatiquement validée par des suites de tests de régression (`./smoke_test.sh` 28/28 tests réussis). |

---

## 1.3 Parties prenantes

| Rôle | Contact / Persona | Attentes |
|---|---|---|
| **Ingénieur Plateforme / Intégrateur** | Administrateur Système | Déploiement rapide et automatisé, flux GitOps déclaratifs, zéro dérive de configuration, procédures de sauvegarde et restauration claires. |
| **Développeur IA / Ingénieur Agents** | Développeur Applicatif | Endpoints unifiés compatibles OpenAI, exposition standardisée d'outils MCP, protection automatique PII, traces d'exécution détaillées. |
| **Auditeur Sécurité** | Responsable Conformité | Aucun secret en clair sur disque, certificats TLS vérifiables sans flags de contournement, IAM au moindre privilège, journalisation d'audit et RBAC strict. |
| **Utilisateur Final** | Utilisateur Métier | Interface de chat intuitive, interrogation instantanée de documents, streaming rapide des réponses, haute disponibilité. |
