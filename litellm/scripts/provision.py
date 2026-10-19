#!/usr/bin/env python3
"""Seed a first LiteLLM SSO login for the admin account after start.sh starts the stack.

Extracted from litellm/provision.sh (originally an inline `python3 -c "..."` heredoc) so it can
be linted/tested like normal Python instead of living inside a bash string.

This script drives Authentik's real flow-executor (see authentik/scripts/oidc_login.py, the
shared helper used to perform automated Authentik flow execution - the same mechanism
smoke_test.sh's own authentik_oidc_authorize() uses) to complete a genuine SSO login. Combined
with the native GENERIC_USER_ROLE_ATTRIBUTE mapping (see authentik/blueprints/20-native-
oidc.yaml and docker-compose.yml), the correct proxy_admin role is assigned by
Authentik itself on every login - including this seeding one - so no direct SQL update of
LiteLLM_UserTable is needed.

Requires DOMAIN to be set in the environment (exported by start.sh from .env), and must be run
from the repo root (docker compose context, for the request URLs to resolve consistently with
the rest of this project's scripts).
"""

import os
import sys

repo_root = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path[:0] = [os.path.join(repo_root, "scripts"), os.path.join(repo_root, "authentik", "scripts")]

from http_client import Session
from oidc_login import oidc_authorize


def required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} must be set and non-empty")
    return value


def main() -> None:
    domain = required_env("DOMAIN")
    admin_password = required_env("UI_PASSWORD")
    sess = Session(verify=False, timeout=15)

    r_start = sess.get(f"https://litellm.{domain}/sso/key/generate", allow_redirects=False, timeout=15)
    authorize_url = r_start.headers.get("Location")
    r_final = oidc_authorize(sess, authorize_url, domain, "admin", admin_password)
    if r_final.status_code != 200 or "login=success" not in r_final.url:
        raise RuntimeError(f"LiteLLM admin SSO login landed on {r_final.url}")
    print("   -> LiteLLM admin SSO login: OK")


if __name__ == "__main__":
    main()
