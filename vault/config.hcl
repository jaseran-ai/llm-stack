storage "file" {
  path = "/vault/data"
}

listener "tcp" {
  address       = "0.0.0.0:8200"
  tls_disable   = 0
  tls_cert_file = "/etc/vault/certs/tls.crt"
  tls_key_file  = "/etc/vault/certs/tls.key"
}

ui = true
disable_mlock = true
