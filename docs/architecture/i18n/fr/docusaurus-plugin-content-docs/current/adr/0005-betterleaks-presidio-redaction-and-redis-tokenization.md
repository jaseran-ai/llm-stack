# ADR 0005 : Biffure Betterleaks Presidio et Tokenisation Redis

* **Statut** : Accepté
* **Décideurs** : Mainteneurs de LLM Stack
* **Date** : 2026-09-25
* **Histoire Technique** : Interception bidirectionnelle des secrets et tokenisation réversible

## Contexte et Problématique

Lors des interactions des développeurs et applications avec les LLMs, des informations sensibles (clés API, tokens d'accès, mots de passe et données personnelles PII) peuvent être accidentellement divulguées dans les prompts ou répétées dans les complétions. Le masquage basique par regex (`[REDACTED]`) brise la syntaxe du code et empêche les outils automatisés d'exploiter les valeurs originales.

## Critères de Décision

* Détection rapide et à faible latence des secrets et PII (en français et en anglais).
* Protection bidirectionnelle (prompts entrants et réponses générées).
* Tokenisation réversible sécurisée permettant aux clients autorisés de restaurer les valeurs initiales.
* Chiffrement Zero-Trust pour le stockage des correspondances de tokens.

## Options Examinées

1. **Garde-fous lourds sous PyTorch (ex: Llama-Guard, NeMo)** : Exige des modèles de plusieurs gigaoctets sur GPU, en conflit avec la portabilité CPU monocarte.
2. **Masquage unidirectionnel** : Remplace les données par des chaînes statiques ; détruit la structure du code et bloque l'exécution d'outils.
3. **Moteur Go Betterleaks + Presidio Analyzer avec stockage Redis chiffré AES-256-GCM** : Binaire Go ultra-rapide pour les regex, modèles spaCy légers pour la NER, et correspondances conservées dans Redis chiffrées en AES-256-GCM côté client.

## Décision Retenue

Option choisie : **Betterleaks + Presidio avec Tokenisation réversible AES-256-GCM**, intégrée via le filtre d'outlet Open WebUI et les garde-fous LiteLLM, avec un endpoint gRPC ExtMcp optionnel pour les passerelles MCP.

### Conséquences Positives

* Les secrets et PII sont biffés avant que les prompts n'atteignent le LLM ou les fournisseurs tiers.
* La tokenisation réversible permet aux applications autorisées de restaurer les valeurs d'origine.
* Les correspondances dans Redis sont chiffrées côté client ; une copie brute de Redis ne livre que du texte chiffré.
* Des métriques Prometheus dédiées et des alertes Alertmanager se déclenchent lors de fuites interceptées.

### Conséquences Négatives

* Introduit une surcharge de latence minime sur les complétions (~15 à 30ms pour l'analyse NLP locale).
