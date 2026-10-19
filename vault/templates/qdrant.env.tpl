# ==============================================================================
# Vault Agent Generated Secrets — Qdrant
# DO NOT EDIT MANUALLY — rendered by vault-agent from secret/data/llm-stack/qdrant
# ==============================================================================

{{ with secret "secret/data/llm-stack/qdrant" }}
QDRANT__SERVICE__API_KEY={{ .Data.data.API_KEY }}
{{ end }}
