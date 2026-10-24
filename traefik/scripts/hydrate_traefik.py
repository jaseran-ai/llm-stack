#!/usr/bin/env python3
"""Hydrate Traefik static and dynamic configuration files from templates.

Reads .env / environment variables to generate traefik/traefik.yml and traefik/dynamic.yml
supporting four TLS modes (internal, custom, http-01, cloudflare-dns01).
"""

import os
import re
import sys


def read_env_file(path='.env'):
    values = {}
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                m = re.match(r'^([A-Z_0-9]+)=(.*)$', line)
                if m:
                    values[m.group(1)] = m.group(2).strip('"\'')
    return values


def main():
    env = read_env_file()
    domain = env.get('DOMAIN', os.environ.get('DOMAIN', 'localhost'))
    tls_mode = env.get('TLS_MODE', os.environ.get('TLS_MODE', 'internal'))

    # Hydrate static configuration (traefik.yml)
    cert_resolvers = ""
    if tls_mode == 'http-01':
        cert_resolvers = """
certificatesResolvers:
  myresolver:
    acme:
      storage: /etc/traefik/acme.json
      httpChallenge:
        entryPoint: web
"""
    elif tls_mode == 'cloudflare-dns01':
        cert_resolvers = """
certificatesResolvers:
  myresolver:
    acme:
      storage: /etc/traefik/acme.json
      dnsChallenge:
        provider: cloudflare
        resolvers:
          - "1.1.1.1:53"
          - "8.8.8.8:53"
"""
    elif tls_mode in ('internal', 'custom'):
        # Static certificate from traefik/certs/tls.crt (internal CA or your own CA, see setup.sh)
        cert_resolvers = ""

    with open('traefik/traefik.yml.template') as f:
        static_tpl = f.read()

    static_out = static_tpl.replace('___TRAEFIK_CERT_RESOLVERS___', cert_resolvers).rstrip() + '\n'
    with open('traefik/traefik.yml', 'w') as f:
        f.write(static_out)

    # Hydrate dynamic configuration (dynamic.yml)
    tls_options = "{}"

    with open('traefik/dynamic.yml.template') as f:
        dynamic_tpl = f.read()

    dynamic_out = dynamic_tpl.replace('${DOMAIN}', domain).replace('___TRAEFIK_TLS_OPTIONS___', tls_options).rstrip() + '\n'
    with open('traefik/dynamic.yml', 'w') as f:
        f.write(dynamic_out)

    print(f"-> Traefik configuration hydrated (DOMAIN={domain}, TLS_MODE={tls_mode})")


if __name__ == '__main__':
    main()
