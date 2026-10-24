# Tutoriel : Consommer l'API LLM avec Python et cURL

Ce tutoriel démontre comment interagir avec la passerelle LiteLLM depuis des applications externes.

---

## 1. Prérequis

Obtenez une clé API. Vous pouvez générer des clés via l'interface LiteLLM ou lire la clé d'administration rendue dans le montage tmpfs en RAM :
```bash
LITELLM_KEY=$(grep "LITELLM_MASTER_KEY=" vault/secrets_ram/litellm.env | cut -d= -f2)
```

---

## 2. Lister les Modèles Disponibles avec cURL

Interrogez l'endpoint `/v1/models` :
```bash
curl -s -X GET "https://litellm.${DOMAIN}/v1/models" \
  -H "Authorization: Bearer ${LITELLM_KEY}" | jq .
```

Exemple de réponse :
```json
{
  "object": "list",
  "data": [
    {
      "id": "lfm2-1.2b-rag",
      "object": "model",
      "owned_by": "llm-stack"
    }
  ]
}
```

---

## 3. Soumettre une Complétion de Chat en Python

Utilisez le SDK officiel Python `openai` (version 1.0+) :

```python
import os
from openai import OpenAI

client = OpenAI(
    api_key=os.environ.get("LITELLM_KEY"),
    base_url="https://litellm.example.local/v1"
)

response = client.chat.completions.create(
    model="lfm2-1.2b-rag",
    messages=[
        {"role": "system", "content": "Tu es un assistant informatique serviable."},
        {"role": "user", "content": "Écris une fonction Python pour calculer la suite de Fibonacci."}
    ],
    temperature=0.7
)

print(response.choices[0].message.content)
```

---

## 4. Vérifier les Garde-fous de Confidentialité

Soumettez un prompt contenant des données sensibles (ex: clé secrète AWS ou adresse email) :
```bash
curl -s -X POST "https://litellm.${DOMAIN}/v1/chat/completions" \
  -H "Authorization: Bearer ${LITELLM_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "lfm2-1.2b-rag",
    "messages": [
      {"role": "user", "content": "Ma clé AWS est AKIAIOSFODNN7EXAMPLE, peux-tu m'\''aider à la révoquer ?"}
    ]
  }'
```

En arrière-plan, Betterleaks Presidio intercepte le prompt, remplace la clé par `<SURROGATE_TOKEN_API_KEY_01>` et garantit que les identifiants bruts ne quittent jamais le périmètre sécurisé.
