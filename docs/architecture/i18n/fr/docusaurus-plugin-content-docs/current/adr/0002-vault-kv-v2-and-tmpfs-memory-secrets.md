# ADR 0002 : Vault KV v2 et Secrets en Mémoire tmpfs

* **Statut** : Accepté
* **Décideurs** : Mainteneurs de LLM Stack
* **Date** : 2026-08-20
* **Histoire Technique** : Durcissement de la sécurité des secrets et élimination de la persistance disque

## Contexte et Problématique

Initialement, les secrets étaient générés dans un fichier racine `.env` ou rendus par Vault Agent dans un dossier hôte sur disque physique. Cela créait des risques de sécurité majeurs : secrets en clair persistant sur les blocs disques, vulnérabilité aux analyses forensiques post-mortem, risque de commit accidentel dans git et exposition transverse entre conteneurs.

## Critères de Décision

* Zéro secret en clair commité dans le gestionnaire de versions.
* Zéro secret en clair écrit sur le stockage physique non volatil.
* Gestion dynamique du cycle de vie des secrets via HashiCorp Vault KV v2.
* Rendu automatisé au runtime sans intervention humaine ni descellement manuel.

## Options Examinées

1. **Fichier `.env` statique sur disque hôte** : Le plus simple, mais risques critiques de fuite, d'analyse forensique et d'absence de piste d'audit.
2. **Déploiement externe OpenBao** : Évalué pour les équipes multi-opérateurs, mais complexité opérationnelle du seal Shamir sur une installation mono-hôte.
3. **Vault KV v2 + rendu tmpfs via Vault Agent** : Provisioning dynamique des secrets via scripts Python dans Vault KV v2, avec rendu par Vault Agent dans un volume `tmpfs` en RAM restreint avec permissions `0700`/`0600`.

## Décision Retenue

Option choisie : **Vault KV v2 + Secrets en mémoire tmpfs**, car elle garantit que les identifiants sensibles résident exclusivement en mémoire volatile et sont purgés lors du redémarrage.

### Conséquences Positives

* Les secrets ne sont jamais écrits sur les blocs de disque physique, empêchant la récupération forensique hors ligne.
* Les permissions de fichiers sont strictement verrouillées (`0700` pour le répertoire, `0600` pour les fichiers).
* Vault Agent rafraîchit en continu les templates et gère la ré-authentification AppRole automatiquement.
* Aucune syntaxe de repli par défaut autorisée dans `docker-compose.yml` (syntaxe stricte `${VAR}` imposée).

### Conséquences Négatives

* Au démarrage à froid, les secrets doivent être rendus par Vault Agent avant que les conteneurs dépendants puissent lire leurs fichiers d'environnement (géré par les sondes de santé des conteneurs).
