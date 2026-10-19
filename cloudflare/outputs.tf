output "tunnel_id" {
  value       = cloudflare_zero_trust_tunnel_cloudflared.stack_tunnel.id
  description = "The ID of the managed Cloudflare Tunnel."
}

output "tunnel_cname" {
  value       = "${cloudflare_zero_trust_tunnel_cloudflared.stack_tunnel.id}.cfargotunnel.com"
  description = "The CNAME target for the Cloudflare Tunnel."
}

output "routed_subdomains" {
  value       = [for sub in var.subdomains : "${sub}.${var.zone_name}"]
  description = "List of fully-qualified domain names routed by the Cloudflare Tunnel."
}
