storage "file" {
  path = "/vault/data"
}

listener "tcp" {
  address       = "0.0.0.0:8200"
  tls_disable   = 0
  tls_cert_file = "/etc/vault/certs/vault.crt"
  tls_key_file  = "/etc/vault/certs/vault.key"
}

ui = true
disable_mlock = true
