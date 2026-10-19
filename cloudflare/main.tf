terraform {
  required_version = ">= 1.5.0"
  required_providers {
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.0"
    }
  }
}

provider "cloudflare" {
  api_token = var.cloudflare_api_token
}

data "cloudflare_zone" "domain" {
  name = var.zone_name
}

resource "cloudflare_zero_trust_tunnel_cloudflared" "stack_tunnel" {
  account_id = var.cloudflare_account_id
  name       = var.tunnel_name
  secret     = var.tunnel_secret
}

resource "cloudflare_zero_trust_tunnel_cloudflared_config" "stack_tunnel_config" {
  account_id = var.cloudflare_account_id
  tunnel_id  = cloudflare_zero_trust_tunnel_cloudflared.stack_tunnel.id

  config {
    dynamic "ingress_rule" {
      for_each = var.subdomains
      content {
        hostname = "${ingress_rule.value}.${var.domain}"
        service  = "http://traefik"
      }
    }

    ingress_rule {
      service = "http_status:404"
    }
  }
}

resource "cloudflare_record" "subdomains" {
  for_each = toset(var.subdomains)

  zone_id = data.cloudflare_zone.domain.id
  name    = each.value
  type    = "CNAME"
  content = "${cloudflare_zero_trust_tunnel_cloudflared.stack_tunnel.id}.cfargotunnel.com"
  proxied = true
  ttl     = 1
}

resource "cloudflare_zone_settings_override" "zone_settings" {
  zone_id = data.cloudflare_zone.domain.id

  settings {
    ssl              = "strict"
    min_tls_version = "1.2"
    tls_1_3         = "on"
    always_use_https = "on"
  }
}

resource "cloudflare_record" "dmarc" {
  count   = var.enable_email_security_records ? 1 : 0
  zone_id = data.cloudflare_zone.domain.id
  name    = "_dmarc"
  type    = "TXT"
  content = "v=DMARC1; p=reject; sp=reject; adkim=s; aspf=s;"
  ttl     = 1
}

resource "cloudflare_record" "caa_letsencrypt" {
  count   = var.enable_email_security_records ? 1 : 0
  zone_id = data.cloudflare_zone.domain.id
  name    = "@"
  type    = "CAA"
  ttl     = 1

  data {
    flags = "0"
    tag   = "issue"
    value = "letsencrypt.org"
  }
}

resource "cloudflare_record" "caa_google" {
  count   = var.enable_email_security_records ? 1 : 0
  zone_id = data.cloudflare_zone.domain.id
  name    = "@"
  type    = "CAA"
  ttl     = 1

  data {
    flags = "0"
    tag   = "issue"
    value = "pki.goog"
  }
}
