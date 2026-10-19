pid_file = "/tmp/vault-agent.pid"

vault {
  address = "https://vault:8200"
  ca_cert = "/etc/vault/certs/tls.crt"
}

auto_auth {
  method "approle" {
    config = {
      role_id_file_path = "/run/secrets/.agent-role-id"
      secret_id_file_path = "/run/secrets/.agent-secret-id"
      remove_secret_id_file_after_reading = false
    }
  }
}

# Authentik account reconciliation (alice + bob)
template {
  source      = "/etc/vault/templates/authentik.env.tpl"
  destination = "/run/secrets/authentik.env"
  error_on_missing_key = true
  perms       = "0640"
  backup      = false
}

# Langfuse (postgres + clickhouse + langfuse + seaweedfs + redis)
template {
  source      = "/etc/vault/templates/langfuse.env.tpl"
  destination = "/run/secrets/langfuse.env"
  perms       = "0600"
}

# LiteLLM (litellm master key + OIDC + UI password + postgres + redis)
template {
  source      = "/etc/vault/templates/litellm.env.tpl"
  destination = "/run/secrets/litellm.env"
  perms       = "0600"
}

# Open-WebUI (webui secret key + qdrant api key)
template {
  source      = "/etc/vault/templates/open-webui.env.tpl"
  destination = "/run/secrets/open-webui.env"
  perms       = "0600"
}

# Grafana (admin password)
template {
  source      = "/etc/vault/templates/grafana.env.tpl"
  destination = "/run/secrets/grafana.env"
  perms       = "0600"
}

# Qdrant (API key)
template {
  source      = "/etc/vault/templates/qdrant.env.tpl"
  destination = "/run/secrets/qdrant.env"
  perms       = "0600"
}

# ClickHouse UI (JWT + RBAC + OIDC)
template {
  source      = "/etc/vault/templates/chouse-ui.env.tpl"
  destination = "/run/secrets/chouse-ui.env"
  perms       = "0600"
}

# SeaweedFS (s3.json)
template {
  source      = "/etc/vault/templates/s3.json.tpl"
  destination = "/run/secrets/s3.json"
  perms       = "0640"
}

# Betterleaks
template {
  source      = "/etc/vault/templates/betterleaks.env.tpl"
  destination = "/run/secrets/betterleaks.env"
  perms       = "0600"
}

