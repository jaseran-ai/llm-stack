# Le Modèle Zero-Trust & les Secrets en Mémoire Vive

Ce document détaille les principes zero-trust et le modèle de gestion des secrets en mémoire vive protégeant la stack LLM.

---

## Principes Zero-Trust Fondamentaux

L'architecture repose sur trois postulats de sécurité :
1. **Le réseau interne est hostile** : Un conteneur ne peut présumer d'un accès sans authentification aux services voisins sous prétexte qu'ils partagent un bridge Docker.
2. **Le stockage physique est persistant et non fiable** : Des secrets en clair écrits sur le disque peuvent être récupérés par analyse forensique ou fuiter lors de sauvegardes.
3. **L'identité doit être vérifiée à chaque étape** : Les cookies de session et tokens Bearer doivent être validés en continu.

---

## L'Architecture de Secrets Zéro Disque

```text
[setup.sh]
    │ (Génération de clés 256 bits aléatoires)
    ▼
[HashiCorp Vault KV v2] (Stockage maître chiffré)
    │
    │ (Auth AppRole via listener HTTPS TLS)
    ▼
[Démon Vault Agent]
    │ (Rendu des templates Consul)
    ▼
[/vault/secrets_ram] ── (Montage tmpfs isolé en RAM, mode 0700)
    │
    ├─► open-webui.env (mode 0600)
    ├─► litellm.env (mode 0600)
    └─► langfuse.env (mode 0600)
```

### Pourquoi le tmpfs ?
* **Zéro Persistance** : Dès l'extinction ou le redémarrage du serveur, le contenu de la RAM s'évapore instantanément. Aucun outil forensique ne peut extraire de mot de passe en clair du disque.
* **Montages Granulaires** : Chaque conteneur ne monte que le fichier `.env` strictement nécessaire à son fonctionnement, empêchant la lecture d'identifiants transverses.
* **Permissions Rigoureuses** : Le dossier est verrouillé à `0700` et les fichiers à `0600`, interdisant l'accès aux utilisateurs non privilégiés.
