# CoreDNS Service — LAN Wildcard DNS Resolution

This directory contains the declarative configuration for the optional **CoreDNS** service in `llm-stack`.

---

## 🌐 Overview & Purpose

When running `llm-stack` on a local area network (LAN) without public DNS or Cloudflare Tunnels, clients must resolve `${DOMAIN}` and all service subdomains (`*.${DOMAIN}`, e.g. `chat.${DOMAIN}`, `authentik.${DOMAIN}`, `grafana.${DOMAIN}`) to the stack host's IP (`${LAN_IP}`).

While **hosts mode** requires every client machine to edit `/etc/hosts` manually, **CoreDNS mode** provides an automated, zero-touch network resolution path:
1. An embedded, ultra-lightweight CoreDNS container runs with `profiles: ["coredns"]`.
2. CoreDNS resolves `${DOMAIN}` and all subdomains (`*.${DOMAIN}`) directly to `${LAN_IP}` using the `template` plugin.
3. All external/public internet DNS queries are forwarded upstream to public resolvers (`1.1.1.1` and `8.8.8.8`).
4. Any device on the LAN configured with the stack host as its DNS resolver can access all `llm-stack` services immediately without modifying local host files.

---

## ⚙️ Configuration & Hydration

CoreDNS configuration is hydrated dynamically by `./setup.sh`:
- Template: [`Corefile.template`](Corefile.template)
- Runtime file: `Corefile` (generated during setup, ignored by Git)

### Corefile Structure

```corefile
.:53 {
    template IN A example.com {
        match "(^|\.)example\.com\.$"
        answer "{{ .Name }} 60 IN A 192.168.1.100"
        fallthrough
    }

    forward . 1.1.1.1 8.8.8.8 {
        max_concurrent 1000
    }

    cache 30
    errors
    log
}
```

---

## 🚀 Activation & Usage

### 1. Enable CoreDNS Mode
Run `setup.sh` with the `--dns-mode=coredns` flag:

```bash
./setup.sh --dns-mode=coredns
```

This sets `DNS_MODE=coredns` and `COMPOSE_PROFILES=coredns` in `.env` and hydrates `coredns/Corefile`.

### 2. Port Binding & Conflicts
CoreDNS binds to `${COREDNS_BIND_IP}:53` (defaulting to `${LAN_IP}`).
On Linux distributions running `systemd-resolved` (which listens on `127.0.0.53:53`), binding specifically to `${LAN_IP}:53` avoids `EADDRINUSE` port conflicts.

### 3. Client Configuration
To use CoreDNS from workstations on your LAN:
- **Option A (Network-wide)**: Set your DHCP router's primary DNS server to `${LAN_IP}`.
- **Option B (Per-client)**: Configure your workstation's network settings to use `${LAN_IP}` as DNS server.

### 4. Verification

Test name resolution using `dig`:

```bash
# Verify wildcard resolution to LAN IP:
dig @<LAN_IP> chat.<DOMAIN> +short

# Verify upstream forwarding:
dig @<LAN_IP> google.com +short
```
