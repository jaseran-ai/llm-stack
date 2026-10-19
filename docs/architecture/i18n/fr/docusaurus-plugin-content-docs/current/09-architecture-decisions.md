# 9. Décisions d'Architecture

Cette section indexe l'ensemble des enregistrements de décision d'architecture (ADR) régissant la stack LLM. Chaque décision est documentée dans le dossier `adr/` selon le format Markdown Any Decision Record (MADR).

---

## 9.1 Index des Enregistrements de Décision

| Identifiant | Titre de la décision | Statut | Date | Déclencheur principal |
|---|---|---|---|---|
| [**ADR 0001**](adr/0001-authentik-unified-identity-and-rbac.md) | Authentik : Identité Unifiée et RBAC | **Accepté** | 2026-08-15 | Unification de l'IdP, d'OIDC et du portail d'applications en un moteur unique. |
| [**ADR 0002**](adr/0002-vault-kv-v2-and-tmpfs-memory-secrets.md) | Vault KV v2 et Secrets en Mémoire tmpfs | **Accepté** | 2026-08-20 | Élimination des secrets en clair sur les blocs de stockage disque physique. |
| [**ADR 0003**](adr/0003-traefik-v3-ingress-and-security-headers.md) | Ingress Traefik v3 et Headers de Sécurité | **Accepté** | 2026-08-22 | Routage Docker natif, chaînage de middlewares et en-têtes HSTS. |
| [**ADR 0004**](adr/0004-internal-tls-and-local-ca-injection.md) | TLS Interne et Injection de l'Autorité Locale | **Accepté** | 2026-10-18 | Élimination des flags de bypass TLS et durcissement HTTPS de Vault. |
| [**ADR 0005**](adr/0005-betterleaks-presidio-redaction-and-redis-tokenization.md) | Biffure Betterleaks Presidio et Tokenisation Redis | **Accepté** | 2026-09-25 | Tokenisation réversible sécurisée avec cache Redis chiffré AES-256-GCM. |
| [**ADR 0006**](adr/0006-seaweedfs-least-privilege-s3-iam.md) | IAM S3 SeaweedFS au Moindre Privilège | **Accepté** | 2026-10-18 | Isolation de l'accès au bucket S3 Langfuse hors des accès admin. |
| [**ADR 0007**](adr/0007-multi-tier-network-segmentation.md) | Segmentation Réseau Multi-Tiers | **Proposé** | 2026-10-18 | Segmentation réseau à 4 tiers isolant les bases de données. |

---

## 9.2 Règles de Gouvernance des ADRs

* **Immuabilité des ADRs acceptés** : Une fois un ADR validé comme `Accepté`, son contexte historique, sa décision et ses motivations ne sont jamais modifiés rétroactivement. Si une décision change, un nouvel ADR de remplacement est rédigé.
* **Cycle de vie des propositions** : Les ADRs créés par des assistants automatisés restent au statut `Proposé` jusqu'à validation explicite par l'utilisateur.
* **Format MADR** : Tout ADR inclut impérativement Statut, Décideurs, Date, Contexte, Options examinées, Décision retenue et Conséquences.
