# ==============================================================================
# Vault Agent Generated Secrets — Open-WebUI
# DO NOT EDIT MANUALLY — rendered by vault-agent from secret/data/llm-stack/open-webui
# ==============================================================================

{{ with secret "secret/data/llm-stack/open-webui" }}
WEBUI_SECRET_KEY={{ .Data.data.WEBUI_SECRET_KEY }}
QDRANT_API_KEY={{ .Data.data.QDRANT_API_KEY }}
{{ end }}

{{ with secret "secret/data/llm-stack/litellm" }}
OPENAI_API_KEY={{ .Data.data.MASTER_KEY }}
OPENAI_API_KEYS={{ .Data.data.MASTER_KEY }}
{{ end }}
