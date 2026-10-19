# 11. Risques et dette technique

Cette section recense les contrôles de sécurité qui atténuent les risques connus, ainsi que les limites qui restent ouvertes par conception.

---

## 11.1 Risques atténués

| Risque | Sévérité | Atténuation |
|---|---|---|
| Secrets écrits en clair sur le disque persistant de l'hôte. | **Élevé** | Vault Agent rend les secrets dans un volume `tmpfs` en mémoire (`vault/secrets_ram/`) avec des permissions `0700`/`0600`. Voir l'[ADR 0002](adr/0002-vault-kv-v2-and-tmpfs-memory-secrets.md). |
| Listener Vault exposé en HTTP non chiffré. | **Élevé** | Listener TLS activé (`tls_disable = 0`) avec certificats SAN ; Traefik vérifie le backend avec l'autorité de certification locale. |
| Drapeaux globaux de contournement TLS (`NODE_TLS_REJECT_UNAUTHORIZED="0"`, `PYTHONHTTPSVERIFY="0"`). | **Élevé** | Drapeaux supprimés ; l'AC locale est injectée dans les runtimes Node.js via `NODE_EXTRA_CA_CERTS`. Voir l'[ADR 0004](adr/0004-internal-tls-and-local-ca-injection.md). |
| Langfuse utilisant des identifiants S3 administrateur. | **Moyen** | Identité dédiée à moindre privilège `langfuse_app`, limitée au bucket `langfuse`. Voir l'[ADR 0006](adr/0006-seaweedfs-least-privilege-s3-iam.md). |
| Points de terminaison réseau privés versionnés dans Git. | **Bas** | Les cibles propres à chaque site vivent dans des points d'extension ignorés par Git (`gatus/endpoints.d/`, `prometheus/targets.d/`, `litellm/custom_models.yaml`). |
| Absence d'enregistrements anti-usurpation e-mail et d'autorisation d'AC (mode Cloudflare). | **Moyen** | Terraform provisionne un enregistrement DMARC strict (`p=reject`) et des enregistrements CAA. |
| Absence d'en-têtes HSTS et TLS 1.0/1.1 acceptés en bordure. | **Moyen** | Middleware Traefik `security-headers@file` et `min_tls_version = "1.2"` côté Cloudflare. Voir l'[ADR 0003](adr/0003-traefik-v3-ingress-and-security-headers.md). |
| Tous les conteneurs sur un unique réseau Docker plat. | **Moyen** | Bases de données et caches isolés sur le réseau `internal-backend` (`internal: true`). Voir l'[ADR 0007](adr/0007-multi-tier-network-segmentation.md). |
| Endpoints de santé publics, images non épinglées, rôle SSO par défaut trop privilégié. | **Moyen** | `/api/health` et `/v1/sys/health` protégés par des routeurs Traefik, toutes les images épinglées par digest SHA-256, `AUTH_SSO_DEFAULT_ROLE: "viewer"` pour CHouse UI. |
| Contournement de la rédaction via des caractères Unicode invisibles ou confusables. | **Moyen** | Betterleaks applique une normalisation NFKC et supprime les séparateurs de largeur nulle avant analyse. |
| Épuisement mémoire via des charges de rédaction surdimensionnées. | **Bas** | Betterleaks rejette les entrées de plus de 500k caractères avec un HTTP 413. |

---

## 11.2 Risques ouverts et limites acceptées

### 1. Déploiement sur un seul nœud
La stack s'exécute sur un seul hôte Docker. Il n'y a pas de haute disponibilité : une panne de l'hôte arrête tous les services jusqu'à leur restauration depuis les sauvegardes (voir `docs/BACKUP_AND_RESTORE.md`).

### 2. Accès au socket Docker
Traefik, Vector et Dozzle montent `/var/run/docker.sock` en lecture seule pour la découverte de services et la collecte des logs. Un accès en lecture seule à l'API Docker expose tout de même les métadonnées et variables d'environnement des conteneurs ; ces services doivent rester derrière le Forward-Auth et ne jamais être exposés directement.

### 3. Autorité de certification interne auto-signée
En `TLS_MODE=internal`, les clients doivent faire confiance à l'AC racine générée localement. Elle est générée à chaque installation par `setup.sh` et n'est jamais versionnée.

### 4. Images maintenues par la communauté
Quelques composants optionnels sont publiés par des mainteneurs individuels plutôt que par le projet amont. Ils sont épinglés par digest et analysés par Trivy, mais reçoivent les correctifs de sécurité au rythme de leur mainteneur.
