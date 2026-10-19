# ==============================================================================
# Vault Agent Generated Secrets — Betterleaks
# DO NOT EDIT MANUALLY — rendered by vault-agent from secret/data/llm-stack/redis & betterleaks
# ==============================================================================

{{ with secret "secret/data/llm-stack/redis" }}
REDIS_AUTH={{ .Data.data.AUTH }}
{{ end }}

{{ with secret "secret/data/llm-stack/betterleaks" }}
TOKEN_ENCRYPTION_KEY={{ .Data.data.TOKEN_ENCRYPTION_KEY }}
{{ end }}
