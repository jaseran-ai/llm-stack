# ADR 0004 : TLS Interne et Injection de l'Autorité Locale

* **Statut** : Accepté
* **Décideurs** : Mainteneurs de LLM Stack
* **Date** : 2026-10-18
* **Histoire Technique** : Durcissement du listener TLS interne de Vault et suppression des flags de contournement

## Contexte et Problématique

Pour établir des communications HTTPS internes entre conteneurs sans chaîne d'autorité de certification publique, les versions antérieures utilisaient des flags globaux de contournement de vérification TLS (`NODE_TLS_REJECT_UNAUTHORIZED="0"`, `PYTHONHTTPSVERIFY="0"`, `SSL_VERIFY="false"`). Cette pratique désactivait totalement la validation cryptographique, rendant les services vulnérables aux attaques de type machine-in-the-middle sur les flux sortants vers Internet (par exemple lors du téléchargement des grilles de coûts de modèles par LiteLLM ou des appels d'APIs par Langfuse).

## Critères de Décision

* Élimination de tous les flags de contournement TLS globaux non sécurisés.
* Chiffrement des canaux de communication internes (notamment le listener Vault).
* Vérification complète des certificats pour les endpoints d'OpenID Connect internes (`https://authentik.${DOMAIN}/...`).
* Préservation stricte de la validation des certificats racines Mozilla pour le trafic externe vers Internet.

## Options Examinées

1. **Flags de contournement globaux** : Simples, mais faille de sécurité critique laissant toutes les connexions HTTPS externes sans validation.
2. **Écrasement du magasin de confiance système via `SSL_CERT_FILE` en Python** : Casse les appels HTTPS publics externes en Python car `SSL_CERT_FILE` remplace l'intégralité des autorités racines.
3. **Injection ciblée dans Node.js (`NODE_EXTRA_CA_CERTS`) + Confiance sélective Python** : Monter le certificat CA local (`traefik/certs/tls.crt`) dans `/etc/ssl/certs/local-ca.crt` et l'injecter spécifiquement dans Node.js via `NODE_EXTRA_CA_CERTS` (qui s'ajoute sans écraser), tout en conservant le magasin public par défaut de Python.

## Décision Retenue

Option choisie : **Injection ciblée de l'autorité locale**, avec activation du TLS interne sur Vault (`tls_disable = 0`), vérification rootCA via `serversTransport` de Traefik, et injection du certificat CA local dans les conteneurs Node.js sans compromettre les vérifications HTTPS externes de Python.

### Conséquences Positives

* Les flags globaux non sécurisés (`NODE_TLS_REJECT_UNAUTHORIZED="0"`, `PYTHONHTTPSVERIFY="0"`) sont éliminés.
* La découverte OIDC interne réussit en TLS avec validation cryptographique rigoureuse.
* Les requêtes vers Internet continuent d'être validées contre les certificats racines publics officiels.
* Le trafic interne vers Vault est 100% chiffré et validé par Traefik.

### Conséquences Négatives

* Nécessite le montage du certificat CA local en lecture seule dans les conteneurs Node.js.

## Mise à jour : séparation des chaînes de confiance d'entrée et interne

Le certificat auto-signé unique (`tls.crt`, utilisé à la fois comme certificat serveur et comme ancre de confiance) a été remplacé par deux chaînes, afin que l'opérateur puisse servir un certificat émis par sa propre AC sans lui exposer de noms internes :

* **AC interne** (`internal-ca.crt`), toujours générée, signe le certificat du listener Vault (`vault`, `localhost`, `127.0.0.1`). Vault, Vault Agent et le `vault-transport` de Traefik lui font confiance.
* **Chaîne d'entrée** (`tls.crt` + `ca.crt`) pour `${DOMAIN}` et `*.${DOMAIN}` : signée par l'AC interne (`TLS_MODE=internal`) ou par l'AC de l'opérateur à partir d'un CSR généré par `./setup.sh --tls-csr` (`TLS_MODE=custom`). `ca.crt` est l'ancre injectée dans les runtimes Node.js et dans la découverte OIDC de Vault.
