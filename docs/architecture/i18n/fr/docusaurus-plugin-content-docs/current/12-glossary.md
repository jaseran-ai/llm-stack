# 12. Glossaire

Cette section référence la **Source Unique de Vérité** pour la terminologie technique et les définitions de composants.

Pour consulter le glossaire complet et maintenu, référez-vous au glossaire racine :

> **Source Canonique** : [`docs/shared/GLOSSARY.md`](https://github.com/jaseran-ai/llm-stack/blob/main/docs/shared/GLOSSARY.md)

---

## Définitions Clés de la Plateforme

* **Authentik** : Fournisseur d'Identité (IdP) unifié assurant l'authentification unique (SSO) et le contrôle d'accès basé sur les rôles (RBAC).
* **Betterleaks** : Moteur de biffure de secrets et PII haute performance en Go et Python avec tokenisation réversible sécurisée.
* **Forward-Auth (Pattern A)** : Patron d'authentification par proxy inverse déléguant la vérification d'accès à Authentik avant de relayer la requête au conteneur cible.
* **OIDC Natif (Pattern B)** : Flux d'autorisation standardisé OpenID Connect OAuth2 négocié directement par les services compatibles.
* **LiteLLM** : Passerelle mandataire unifiée compatible OpenAI gérant la répartition de charge, le suivi des dépenses et les replis de modèles.
* **Langfuse** : Plateforme d'observabilité LLMOps traçant les prompts, les évaluations, la latence et les coûts en tokens.
* **SeaweedFS** : Stockage objet S3 sous licence Apache 2.0 offrant un accès signé AWS SigV4 et des politiques IAM granulaires.
* **Vault** : Moteur de secrets HashiCorp Vault administrant les chemins secrets KV v2 et rendant les fichiers de configuration en mémoire vive (`tmpfs`).
