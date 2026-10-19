#!/usr/bin/env python3
"""
Generate an O'Reilly-style technical architecture diagram in SVG format.
Clean, sober, publication-grade black & white with slate blue accents.
"""

def generate_svg():
    width = 1200
    height = 840

    svg = []
    svg.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="100%" style="background-color: #ffffff; font-family: -apple-system, BlinkMacSystemFont, \'Segoe UI\', Helvetica, Arial, sans-serif;">')

    # Definitions (markers, filters)
    svg.append('''
  <defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#334155" />
    </marker>
    <marker id="arrow-blue" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#2563eb" />
    </marker>
    <marker id="arrow-green" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 1.5 L 8 5 L 0 8.5 z" fill="#059669" />
    </marker>
    <filter id="card-shadow" x="-3%" y="-6%" width="106%" height="114%" filterUnits="userSpaceOnUse">
      <feDropShadow dx="0" dy="2" stdDeviation="2" flood-color="#0f172a" flood-opacity="0.04" />
    </filter>
  </defs>
''')

    # Header / Title Block (O'Reilly Technical Figure Style)
    svg.append(f'''
  <!-- Title Block -->
  <rect x="30" y="25" width="{width - 60}" height="45" fill="#f8fafc" stroke="#e2e8f0" stroke-width="1" rx="4" />
  <text x="45" y="46" font-size="14" font-weight="700" fill="#0f172a" letter-spacing="0.5">FIGURE 1-1. LLM STACK RUNTIME TOPOLOGY &amp; SERVICE INTERCONNECTIONS</text>
  <text x="45" y="61" font-size="11" font-weight="400" fill="#64748b">Declarative single-machine containerized architecture with unified Authentik SSO, local CPU inference, and RAM-backed secrets.</text>
''')

    # Helper function for rendering a tier container
    def render_tier_box(x, y, w, h, tier_num, tier_title):
        return f'''
  <g class="tier-box">
    <rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#fafbfc" stroke="#cbd5e1" stroke-width="1" stroke-dasharray="5 3" rx="6" />
    <rect x="{x + 12}" y="{y - 10}" width="{len(f"TIER {tier_num}: {tier_title}") * 7 + 24}" height="20" fill="#f1f5f9" stroke="#94a3b8" stroke-width="1" rx="3" />
    <text x="{x + 20}" y="{y + 4}" font-size="10" font-weight="700" fill="#334155" letter-spacing="0.8">TIER {tier_num}: {tier_title.upper()}</text>
  </g>'''

    # Helper function for rendering a service card
    def render_card(x, y, w, h, name, subtitle, port_tag="", accent_color="#1e293b", badge=""):
        badge_svg = ""
        if badge:
            badge_w = len(badge) * 5.8 + 10
            badge_svg = f'<rect x="{x + w - badge_w - 10}" y="{y + h - 22}" width="{badge_w}" height="15" fill="#f8fafc" stroke="#cbd5e1" stroke-width="0.8" rx="2" /><text x="{x + w - 10 - badge_w/2}" y="{y + h - 11}" font-size="8.5" font-weight="600" fill="#475569" text-anchor="middle">{badge}</text>'
        
        port_svg = ""
        if port_tag:
            port_svg = f'<text x="{x + 12}" y="{y + h - 11}" font-size="9" font-family="ui-monospace, monospace" font-weight="600" fill="#0284c7">{port_tag}</text>'

        return f'''
  <g class="service-card" filter="url(#card-shadow)">
    <rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#ffffff" stroke="#1e293b" stroke-width="1.25" rx="4" />
    <path d="M {x} {y + 4} Q {x} {y} {x + 4} {y} L {x + w - 4} {y} Q {x + w} {y} {x + w} {y + 4} L {x + w} {y + 4} L {x} {y + 4} Z" fill="{accent_color}" />
    <text x="{x + 12}" y="{y + 24}" font-size="13" font-weight="700" fill="#0f172a">{name}</text>
    <text x="{x + 12}" y="{y + 39}" font-size="10" font-weight="400" fill="#475569">{subtitle}</text>
    {badge_svg}
    {port_svg}
  </g>'''

    # Helper function for labeled connector arrows
    def render_arrow(x1, y1, x2, y2, label="", color="#334155", marker="url(#arrow)", dash=""):
        dash_attr = f'stroke-dasharray="{dash}"' if dash else ""
        res = [f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="1.4" marker-end="{marker}" {dash_attr} />']
        if label:
            mx = (x1 + x2) / 2
            my = (y1 + y2) / 2
            lbl_w = len(label) * 5.8 + 12
            res.append(f'<rect x="{mx - lbl_w/2}" y="{my - 8}" width="{lbl_w}" height="16" fill="#ffffff" stroke="#cbd5e1" stroke-width="0.8" rx="2" />')
            res.append(f'<text x="{mx}" y="{my + 3.5}" font-size="9" font-weight="500" fill="#334155" text-anchor="middle">{label}</text>')
        return "\n".join(res)

    def render_poly_arrow(points, label="", color="#334155", marker="url(#arrow)"):
        pts_str = " ".join([f"{p[0]},{p[1]}" for p in points])
        res = [f'<polyline points="{pts_str}" fill="none" stroke="{color}" stroke-width="1.4" marker-end="{marker}" />']
        if label and len(points) >= 2:
            p_mid1 = points[len(points)//2 - 1]
            p_mid2 = points[len(points)//2]
            mx = (p_mid1[0] + p_mid2[0]) / 2
            my = (p_mid1[1] + p_mid2[1]) / 2
            lbl_w = len(label) * 5.8 + 12
            res.append(f'<rect x="{mx - lbl_w/2}" y="{my - 8}" width="{lbl_w}" height="16" fill="#ffffff" stroke="#cbd5e1" stroke-width="0.8" rx="2" />')
            res.append(f'<text x="{mx}" y="{my + 3.5}" font-size="9" font-weight="500" fill="#334155" text-anchor="middle">{label}</text>')
        return "\n".join(res)

    # ==========================================================================
    # TIER 1: INGRESS & IDENTITY
    # ==========================================================================
    svg.append(render_tier_box(30, 95, 1140, 115, 1, "Ingress, Identity & Traffic Routing"))

    # Client Entry Box
    svg.append(f'''
  <g class="client-box">
    <rect x="50" y="125" width="160" height="60" fill="#f8fafc" stroke="#475569" stroke-width="1.2" stroke-dasharray="4 2" rx="4" />
    <text x="130" y="150" font-size="12" font-weight="700" fill="#0f172a" text-anchor="middle">Browser / API Client</text>
    <text x="130" y="166" font-size="9.5" font-weight="400" fill="#64748b" text-anchor="middle">hosts | CoreDNS | Cloudflare</text>
  </g>''')

    # Traefik Card
    svg.append(render_card(270, 122, 230, 68, "Traefik Proxy", "Reverse Proxy & SSL Ingress", "TCP:80/443", "#0f172a", "CORE ROUTER"))

    # Authentik Card
    svg.append(render_card(570, 122, 250, 68, "Authentik SSO", "Identity Provider (IdP & Outpost)", "HTTP:9000", "#2563eb", "AUTH & RBAC"))

    # Vault Card
    svg.append(render_card(890, 122, 260, 68, "HashiCorp Vault", "Secrets Engine & RAM tmpfs Link", "HTTPS:8200", "#7c3aed", "SECURITY"))

    # Connectors Tier 1
    svg.append(render_arrow(210, 155, 270, 155, "HTTPS :443"))
    svg.append(render_arrow(500, 145, 570, 145, "Forward-Auth", "#2563eb", "url(#arrow-blue)"))
    svg.append(render_arrow(570, 165, 500, 165, "Auth Token", "#059669", "url(#arrow-green)"))
    svg.append(render_arrow(820, 155, 890, 155, "OIDC Auth", "#7c3aed"))

    # ==========================================================================
    # TIER 2: CLIENT INTERFACES & WORKSPACES
    # ==========================================================================
    svg.append(render_tier_box(30, 235, 1140, 115, 2, "Interactive Applications & User Workspaces"))

    svg.append(render_card(150, 260, 270, 68, "Open-WebUI", "Chat, RAG Knowledge & Admin", "HTTP:8080", "#0284c7", "FORWARD-AUTH"))
    svg.append(render_card(490, 260, 220, 68, "SearXNG", "Privacy Metasearch Engine", "HTTP:8080", "#0284c7", "FORWARD-AUTH"))
    svg.append(render_card(780, 260, 250, 68, "Authentik Dashboard", "User App Launcher & MFA", "HTTP:9000", "#2563eb", "OIDC PORTAL"))

    # Ingress to Tier 2
    svg.append(render_poly_arrow([(350, 190), (350, 225), (285, 225), (285, 260)], "chat.${DOMAIN}"))
    svg.append(render_poly_arrow([(420, 190), (420, 225), (600, 225), (600, 260)], "searxng.${DOMAIN}"))

    # Open-WebUI to SearXNG
    svg.append(render_arrow(420, 294, 490, 294, "JSON API", "#0284c7"))

    # ==========================================================================
    # TIER 3: LLM GATEWAY & INFERENCE ENGINE
    # ==========================================================================
    svg.append(render_tier_box(30, 375, 1140, 120, 3, "LLM Gateway, Routing & Local Inference"))

    svg.append(render_card(150, 405, 280, 70, "LiteLLM Gateway", "Model Router, Budgets & Governance", "HTTP:4000", "#d97706", "NATIVE OIDC"))
    svg.append(render_card(490, 405, 270, 70, "Ollama Inference", "CPU/GPU Model (lfm2.5-thinking)", "TCP:11434", "#16a34a", "LOCAL ENGINE"))
    svg.append(render_card(810, 405, 250, 70, "Betterleaks / Presidio", "Reversible PII Anonymization", "HTTP:8000", "#7c3aed", "GUARDRAILS"))

    # Connectors Tier 2 -> Tier 3
    svg.append(render_arrow(285, 328, 285, 405, "OpenAI API / Prompt", "#d97706"))

    # LiteLLM -> Ollama & Betterleaks
    svg.append(render_arrow(430, 435, 490, 435, "Inference", "#16a34a"))
    svg.append(render_arrow(430, 455, 810, 455, "PII Masking", "#7c3aed"))

    # ==========================================================================
    # TIER 4: DATA, STATE & VECTOR STORAGE
    # ==========================================================================
    svg.append(render_tier_box(30, 520, 1140, 125, 4, "Data, Knowledge & Storage Infrastructure (internal-backend)"))

    svg.append(render_card(50, 550, 200, 72, "Qdrant", "Vector Database (RAG)", "TCP:6333", "#0891b2", "EMBEDDINGS"))
    svg.append(render_card(275, 550, 205, 72, "PostgreSQL 18", "Relational Identity & State", "TCP:5432", "#1d4ed8", "PRIMARY DB"))
    svg.append(render_card(505, 550, 195, 72, "Redis 8", "In-Memory Cache & Tasks", "TCP:6379", "#dc2626", "CACHE / BROKER"))
    svg.append(render_card(725, 550, 205, 72, "ClickHouse", "Columnar Analytics DB", "HTTP:8123", "#eab308", "ANALYTICS"))
    svg.append(render_card(955, 550, 200, 72, "SeaweedFS", "Distributed S3 Storage", "HTTP:8333", "#059669", "OBJECT STORE"))

    # Open-WebUI -> Qdrant
    svg.append(render_poly_arrow([(180, 328), (180, 505), (150, 505), (150, 550)], "Vector Search", "#0891b2"))

    # ==========================================================================
    # TIER 5: OBSERVABILITY & METRICS PIPELINE
    # ==========================================================================
    svg.append(render_tier_box(30, 670, 1140, 125, 5, "Observability, Telemetry & Operations"))

    svg.append(render_card(50, 700, 200, 72, "Langfuse", "LLM Tracing & Eval", "HTTP:3000", "#ea580c", "NATIVE OIDC"))
    svg.append(render_card(275, 700, 205, 72, "Prometheus", "Metrics Scraper & Alerts", "HTTP:9090", "#e11d48", "FORWARD-AUTH"))
    svg.append(render_card(505, 700, 195, 72, "Grafana", "Visual Dashboards", "HTTP:3000", "#f59e0b", "FORWARD-AUTH"))
    svg.append(render_card(725, 700, 205, 72, "Loki & Vector", "Log TSDB & Shipper", "TCP:3100", "#84cc16", "LOG PIPELINE"))
    svg.append(render_card(955, 700, 200, 72, "Gatus & Dozzle", "Health & Container Logs", "HTTP:8080", "#06b6d4", "FORWARD-AUTH"))

    # LiteLLM -> Langfuse
    svg.append(render_poly_arrow([(210, 475), (210, 660), (150, 660), (150, 700)], "OTel / Traces", "#ea580c"))

    # Footer note
    svg.append(f'''
  <!-- Footer Note -->
  <text x="35" y="{height - 18}" font-size="9.5" font-weight="400" fill="#94a3b8">Note: All ingress traffic terminates at Traefik with automatic TLS. Database backends are strictly isolated on the internal-backend network (internal: true).</text>
  <text x="{width - 35}" y="{height - 18}" font-size="9.5" font-weight="500" fill="#64748b" text-anchor="end">LLM Stack Architecture • 100% As-Code</text>
''')

    svg.append('</svg>')
    return "\n".join(svg)

if __name__ == "__main__":
    with open("assets/architecture-overview.svg", "w", encoding="utf-8") as f:
        f.write(generate_svg())
    print("Generated assets/architecture-overview.svg successfully!")
