# Exécuter des Sauvegardes Chiffrées & des Restaurations Ciblées

Ce guide explique comment réaliser des sauvegardes atomiques de toutes les bases de la stack et exécuter des restaurations de secours.

---

## 1. Créer une Sauvegarde Chiffrée

Le script automatisé réalise un dump des bases relationnelles, capture les instantanés vectoriels, archive les volumes et chiffre l'ensemble avec GnuPG AES-256 :

```bash
./backup.sh
```

### Données sauvegardées :
* **Bases de données PostgreSQL** : Dump SQL complet via `pg_dumpall` (couvrant Authentik, LiteLLM, Langfuse, CHouse UI).
* **Base vectorielle Qdrant** : Instantanés des collections à l'instant T.
* **Volumes de stockage** : Métadonnées SeaweedFS S3 et état de Vault (`vault_data`).
* **Matériel de déverrouillage Vault** : Copie chiffrée de `.vault_keys.json`.

L'archive résultante est enregistrée sous `backups/backup_YYYYMMDD_HHMMSS.tar.gz.gpg` avec permissions `0700`.

---

## 2. Restaurer depuis une Sauvegarde

Pour restaurer la plateforme vers un état antérieur sain :

1. Repérez l'archive de sauvegarde souhaitée dans `backups/`.
2. Lancez le script de restauration avec son chemin et sa somme de contrôle SHA256 :
   ```bash
   ./restore.sh --archive backups/backup_20261018_100000.tar.gz.gpg
   ```
3. Saisissez la `BACKUP_PASSPHRASE` générée lors du `./setup.sh`.
4. Le script de restauration procède automatiquement aux étapes suivantes :
   * Validation de l'intégrité de l'archive avant toute modification des services.
   * Pause propre des conteneurs écrivains (`litellm`, `langfuse-worker`, `authentik-worker`).
   * Restauration des schémas PostgreSQL, instantanés Qdrant et métadonnées SeaweedFS.
   * Vérification de la cohérence des bases et redémarrage des applications.
   * Lancement de `./smoke_test.sh` pour confirmer le rétablissement complet.

---

## 3. Rollbacks Ciblés pour Langfuse

Pour restaurer uniquement les traces LLMOps sans impacter l'authentification ni les autres services :
```bash
python3 scripts/langfuse_snapshot.py rollback --archive backups/langfuse_snapshot_latest.tar.gz.gpg
```
Cette commande exécute un rollback ciblé des données Langfuse en préservant la disponibilité globale de la plateforme.
