# ==============================================================================
# Vault Agent Generated Secrets — Grafana
# DO NOT EDIT MANUALLY — rendered by vault-agent from secret/data/llm-stack/grafana
# ==============================================================================

{{ with secret "secret/data/llm-stack/grafana" }}
GF_SECURITY_ADMIN_PASSWORD={{ .Data.data.ADMIN_PASSWORD }}
{{ end }}
