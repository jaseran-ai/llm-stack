# ==============================================================================
# Vault Agent Generated Secrets — Authentik test accounts
# DO NOT EDIT MANUALLY — rendered by vault-agent from secret/data/llm-stack/authentik
# ==============================================================================

{{ with secret "secret/data/llm-stack/authentik" }}
ALICE_PASSWORD={{ .Data.data.ALICE_PASSWORD }}
BOB_PASSWORD={{ .Data.data.BOB_PASSWORD }}
{{ end }}
