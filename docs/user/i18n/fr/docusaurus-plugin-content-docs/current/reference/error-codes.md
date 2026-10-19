# Codes d'Erreur & Décisions

Ce document détaille les codes de réponse HTTP, les formats d'erreur et les indicateurs de décision retournés par les endpoints de la stack LLM.

---

## 1. Codes de Statut HTTP

| Statut HTTP | Nom | Signification & Déclencheur | Résolution |
|---|---|---|---|
| **200** | `OK` | Requête traitée avec succès. | Fonctionnement nominal. |
| **400** | `Bad Request` | JSON malformé ou paramètres obligatoires manquants (`model`, `messages`). | Vérifier la syntaxe contre la référence d'API. |
| **401** | `Unauthorized` | Bearer token manquant ou invalide. | Fournir une clé d'API valide dans l'en-tête `Authorization`. |
| **403** | `Forbidden` | Privilèges de groupe insuffisants (ex: non-admin accédant à Dozzle ou CHouse UI). | Vérifier l'affectation de groupe Authentik (`admins` vs `users`). |
| **404** | `Not Found` | Modèle ou endpoint demandé introuvable. | Interroger `GET /v1/models` pour vérifier les alias actifs. |
| **429** | `Too Many Requests` | Quota budgétaire dépassé ou limitation de débit chez le fournisseur upstream. | LiteLLM active automatiquement un modèle de repli si configuré. |
| **500** | `Internal Error` | Échec upstream ou plantage de conteneur. | Inspecter les logs via Dozzle (`https://logs.${DOMAIN}`). |
| **502 / 503** | `Bad Gateway` | Service cible en cours de démarrage ou indisponible. | Vérifier l'état sur la page Gatus (`https://status.${DOMAIN}`). |

---

## 2. Indicateurs de Décision des Garde-fous

Lorsque Betterleaks analyse un prompt, des en-têtes HTTP indiquent l'issue de l'inspection :

* `X-Betterleaks-Action: pass` — Le prompt ne contenait aucun secret ni PII détectable.
* `X-Betterleaks-Action: anonymize` — Les entités identifiées ont été neutralisées et substituées par des surrogate tokens.
* `X-Betterleaks-Action: block` — Le prompt contenait une fuite critique et a été immédiatement rejeté.
