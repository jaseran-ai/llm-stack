# ADR 0006 : IAM S3 SeaweedFS au Moindre Privilège

* **Statut** : Accepté
* **Décideurs** : Mainteneurs de LLM Stack
* **Date** : 2026-10-18
* **Histoire Technique** : Délimitation IAM au moindre privilège pour les clients S3

## Contexte et Problématique

SeaweedFS assure le stockage objet compatible S3. Auparavant, tous les services (y compris Langfuse et les scripts de tests smoke) partageaient les identifiants d'administration globale `seaweed_admin`, qui possédaient les droits `Admin` sur l'ensemble des buckets et configurations. Une compromission de Langfuse aurait permis la modification ou la suppression de tous les buckets de stockage.

## Critères de Décision

* Principe du moindre privilège (PoLP).
* Restreindre les identifiants applicatifs strictement à leur bucket dédié (`langfuse`).
* Empêcher l'accès applicatif aux APIs d'administration S3 ou aux fonctions de gestion du filer.
* Provisioning automatisé via Vault KV v2.

## Options Examinées

1. **Identifiants d'administration partagés** : Clé unique pour tous les services. Viole les règles de gouvernance de sécurité.
2. **Instance MinIO dédiée par bucket** : Trop lourd en ressources système.
3. **IAM SeaweedFS déclaratif avec portée par bucket** : Configurer une identité dédiée `langfuse_app` avec des actions explicites (`Read:langfuse`, `Write:langfuse`, `List:langfuse`, `Tagging:langfuse`) sans droits `Admin`, en réservant `seaweed_admin` à la maintenance.

## Décision Retenue

Option choisie : **Identité IAM SeaweedFS délimitée (`langfuse_app`)**, générée lors du `setup.sh`, enregistrée dans Vault KV v2 et injectée dans le conteneur Langfuse via un volume tmpfs en RAM.

### Conséquences Positives

* Une application compromise au niveau du code ne peut pas sortir du périmètre du bucket `langfuse`.
* Les opérations administratives (`Admin`) sont bloquées par le moteur d'autorisation SigV4 de SeaweedFS.
* Les tests automatisés vérifient que `langfuse_app` ne peut manipuler que ses propres objets.

### Conséquences Négatives

* Nécessite la gestion de deux paires d'identifiants S3 dans Vault KV v2.
