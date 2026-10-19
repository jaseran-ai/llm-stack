#!/usr/bin/env python3
"""Wait until the embedded Authentik outpost serves the configured forward-auth endpoint.

The embedded outpost bindings, host configuration, and brand domain are declared
declaratively via authentik/blueprints/99-embedded-outpost.yaml.

Applying or updating the outpost enqueues asynchronous reconciliation tasks in
authentik-worker. Container health and blueprint application do not guarantee
that the embedded Go outpost daemon has already loaded the route table into
memory. This probe waits until the Traefik forward-auth endpoint responds with HTTP 302
redirecting to https://authentik.${DOMAIN}.

Requires AUTHENTIK_BASE_URL and DOMAIN to be set in the environment.
"""

import os
import sys
import time
from urllib import error

from http_client import request_json

FORWARD_AUTH_PATH = "/outpost.goauthentik.io/auth/traefik"
FORWARD_AUTH_TIMEOUT_SECONDS = 600


def base_url() -> str:
    """Return the explicitly configured Authentik API base URL."""
    return os.environ["AUTHENTIK_BASE_URL"].rstrip("/")


def wait_for_forward_auth(
    domain: str,
    timeout_seconds: int = FORWARD_AUTH_TIMEOUT_SECONDS,
    retry_interval: int = 2,
) -> None:
    """Wait until the embedded outpost serves the configured proxy provider."""
    forwarded_host = f"logs.{domain}"
    expected_location_prefix = f"https://authentik.{domain}/"
    headers = {
        "X-Original-URL": f"https://{forwarded_host}/",
        "X-Forwarded-Host": forwarded_host,
        "X-Forwarded-Proto": "https",
    }
    last_result = "no response"
    attempts = 0
    deadline = time.monotonic() + timeout_seconds

    while True:
        attempts += 1
        try:
            response = request_json(
                "GET",
                f"{base_url()}{FORWARD_AUTH_PATH}",
                headers=headers,
                follow_redirects=False,
                timeout=10,
            )
            location = response.headers.get("Location", "")
            last_result = f"HTTP {response.status_code} Location={location or '<missing>'}"
            if response.status_code == 302 and location.startswith(expected_location_prefix):
                print(f"   -> Embedded outpost Forward-Auth ready after {attempts} attempt(s).")
                return
        except (error.URLError, TimeoutError) as exc:
            last_result = f"request error: {exc}"

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        time.sleep(min(retry_interval, remaining))

    raise RuntimeError(
        f"Embedded outpost Forward-Auth did not become ready within {timeout_seconds} seconds "
        f"after {attempts} attempts ({last_result})."
    )


def main() -> None:
    domain = os.environ["DOMAIN"]
    wait_for_forward_auth(domain)


if __name__ == "__main__":
    main()
