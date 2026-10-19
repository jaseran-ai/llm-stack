variable "cloudflare_api_token" {
  type        = string
  description = "Cloudflare API token with Account Cloudflare Tunnel (Edit) and Zone DNS (Edit) permissions."
  sensitive   = true
}

variable "cloudflare_account_id" {
  type        = string
  description = "Cloudflare Account ID (32-character hex string)."

  validation {
    condition     = can(regex("^[a-f0-9]{32}$", var.cloudflare_account_id))
    error_message = "The cloudflare_account_id must be a 32-character hexadecimal string."
  }
}

variable "zone_name" {
  type        = string
  description = "Cloudflare DNS zone root (e.g. example.com). May differ from 'domain' when services are served under a subdomain zone like example.com."
  default     = "example.com"

  validation {
    condition     = can(regex("^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+$", var.zone_name))
    error_message = "The zone_name must be a valid lowercase domain format (e.g. example.com)."
  }
}

variable "domain" {
  type        = string
  description = "Domain for service subdomains (e.g. example.com). Subdomains will be <name>.<domain>."
  default     = "example.com"

  validation {
    condition     = can(regex("^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+$", var.domain))
    error_message = "The domain must be a valid lowercase domain format (e.g. example.com)."
  }
}

variable "tunnel_name" {
  type        = string
  description = "Name for the Cloudflare Zero Trust Tunnel."
  default     = "llm-stack-tunnel"

  validation {
    condition     = length(trimspace(var.tunnel_name)) > 0
    error_message = "The tunnel_name must not be empty."
  }
}

variable "tunnel_secret" {
  type        = string
  description = "Secret key (base64) for the Cloudflare Tunnel."
  sensitive   = true
}

variable "subdomains" {
  type        = list(string)
  description = "List of subdomains to route to Traefik via Cloudflare Tunnel."
  default = [
    "chat",
    "authentik",
    "litellm",
    "langfuse",
    "grafana",
    "logs",
    "searxng",
    "s3",
    "s3-console",
    "clickhouse",
    "qdrant",
    "status",
    "vault",
    "traefik",
    "alertmanager",
    "home",
    "docs",
    "arch"
  ]

  validation {
    condition     = length(var.subdomains) > 0
    error_message = "The subdomains list must contain at least one subdomain."
  }
}

variable "enable_email_security_records" {
  type        = bool
  description = "Whether to manage strict DMARC and CAA records for the domain."
  default     = true
}
