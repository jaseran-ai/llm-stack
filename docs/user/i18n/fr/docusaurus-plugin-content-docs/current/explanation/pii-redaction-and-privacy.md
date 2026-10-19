# La Biffure des PII & la Tokenisation Réversible Sécurisée

Ce document détaille l'architecture des garde-fous de confidentialité et du système de tokenisation de la plateforme.

---

## Le Défi : Confidentialité vs. Utilité pour le Développeur

Lorsque des ingénieurs ou des applications interagissent avec des modèles d'IA :
* Coller des identifiants bruts ou des données personnelles dans des prompts engendre des infractions de conformité (RGPD, HIPAA, SOC 2) et des risques d'exfiltration.
* Cependant, le masquage destructif brut (`[REDACTED]`) brise le code source et empêche les outils automatisés d'exploiter la réponse.

---

## Pipeline de Détection à Double Moteur

La stack LLM intègre un pipeline hybride à deux étages dans `betterleaks-presidio` :

### 1. Analyse par Motifs à Haute Cadence (Moteur Go Betterleaks)
Un microservice compilé en Go analyse le texte d'entrée contre des milliers de signatures régulières ciblant :
* Les identifiants de cloud providers (AWS, GCP, Azure).
* Les jetons d'authentification (GitHub, Slack, Stripe, OpenAI).
* Les clés cryptographiques privées (RSA, Ed25519, certificats PEM).

### 2. Reconnaissance Contextuelle d'Entités Nommées (Presidio Analyzer)
Un service Python appuyé par des modèles NLP spaCy examine le contexte en langage naturel pour repérer :
* Les noms de personnes (`PERSON`).
* Les adresses email (`EMAIL_ADDRESS`).
* Les numéros de téléphone (`PHONE_NUMBER`).
* Les coordonnées postales et numéros IBAN.
* Les modèles sont chargés pour l'**anglais** (`en_core_web_sm`) et le **français** (`fr_core_news_sm`).

---

## Tokenisation Réversible Sécurisée

Au lieu de détruire les informations sensibles, le service applique la **Tokenisation Réversible Sécurisée** :

1. **Substitution par Surrogate** : Une clé d'API comme `ghp_ABC123456789` est remplacée par un jeton surrogate aléatoire : `<SURROGATE_TOKEN_API_KEY_01>`.
2. **Chiffrement AES-256-GCM Côté Client** : La correspondance entre `ghp_ABC123456789` et `<SURROGATE_TOKEN_API_KEY_01>` est chiffrée avec une clé AES 256 bits obtenue auprès de HashiCorp Vault.
3. **Stockage Éphémère Chiffré** : Le texte chiffré est conservé dans Redis avec une durée de vie (TTL) automatique. Même en cas de dump mémoire de Redis, aucun secret en clair n'apparaît.
4. **Dé-anonymisation** : Une fois la réponse produite, un client autorisé peut interroger `/v1/deanonymize` pour restaurer la valeur d'origine de manière transparente.
