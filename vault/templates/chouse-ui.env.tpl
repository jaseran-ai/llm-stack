# ==============================================================================
# Vault Agent Generated Secrets — ClickHouse UI (chouse-ui)
# DO NOT EDIT MANUALLY — rendered by vault-agent from secret/data/llm-stack/chouse-ui
# ==============================================================================

{{ with secret "secret/data/llm-stack/chouse-ui" }}
JWT_SECRET={{ .Data.data.JWT_SECRET }}
RBAC_ENCRYPTION_KEY={{ .Data.data.RBAC_ENCRYPTION_KEY }}
RBAC_ENCRYPTION_SALT={{ .Data.data.RBAC_ENCRYPTION_SALT }}
AUTH_SSO_PROVIDERS_AUTHENTIK_CLIENT_SECRET={{ .Data.data.OIDC_CLIENT_SECRET }}
{{ end }}
