# Explications des Concepts

La section Explications propose des vues d'ensemble conceptuelles, les motivations architecturales et les réflexions de fond guidant la conception de la stack LLM.

---

* [**La Biffure des PII & la Tokenisation Réversible Sécurisée**](pii-redaction-and-privacy.md)
  Comment la détection hybride (regex + spaCy NER) et le chiffrement AES-256-GCM côté client protègent les données sensibles.

* [**Le Modèle Zero-Trust & les Secrets en Mémoire Vive**](zero-trust-model.md)
  Comment la plateforme applique le zéro-disque pour les secrets, le TLS interne et le moindre privilège IAM.
