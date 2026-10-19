# ==============================================================================
# Vault Agent Generated Secrets — LiteLLM
# DO NOT EDIT MANUALLY — rendered by vault-agent from secret/data/llm-stack/litellm
# ==============================================================================

{{ with secret "secret/data/llm-stack/litellm" }}
LITELLM_MASTER_KEY={{ .Data.data.MASTER_KEY }}
UI_PASSWORD={{ .Data.data.UI_PASSWORD }}
GENERIC_CLIENT_SECRET={{ .Data.data.OIDC_CLIENT_SECRET }}
{{ end }}

{{ with secret "secret/data/llm-stack/postgres" }}
DATABASE_URL=postgresql://postgres:{{ .Data.data.POSTGRES_PASSWORD }}@postgres:5432/postgres
{{ end }}

{{ with secret "secret/data/llm-stack/redis" }}
REDIS_AUTH={{ .Data.data.AUTH }}
{{ end }}

{{ with secret "secret/data/llm-stack/langfuse" }}
LANGFUSE_PUBLIC_KEY={{ .Data.data.INIT_PROJECT_PUBLIC_KEY }}
LANGFUSE_SECRET_KEY={{ .Data.data.INIT_PROJECT_SECRET_KEY }}
{{ end }}
