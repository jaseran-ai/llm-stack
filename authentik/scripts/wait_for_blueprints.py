#!/usr/bin/env python3
"""Wait for Authentik custom blueprints and serialize recovery applies.

Authentik discovers mounted blueprints asynchronously. Several blueprints in this
stack also update proxy providers, which can trigger concurrent embedded-outpost
permission refreshes and PostgreSQL deadlocks. Recovery applies therefore run one
at a time, and the next blueprint is not submitted until the current one succeeds.

Requires AUTHENTIK_BOOTSTRAP_TOKEN to be set in the environment.
"""

import os
import sys
import time
from collections.abc import Callable

from http_client import request_json

API_ATTEMPTS = 60
PASSIVE_ATTEMPTS = 60
APPLY_ATTEMPTS = 3
APPLY_STATUS_ATTEMPTS = 300
POLL_INTERVAL = 1
APPLY_RETRY_DELAY = 3


def base_url() -> str:
    """Return the explicitly configured Authentik API base URL."""
    return os.environ["AUTHENTIK_BASE_URL"].rstrip("/")


def get_custom_blueprints(headers: dict) -> dict:
    """Return custom blueprint identifiers mapped to their names and states."""
    response = request_json(
        "GET",
        f"{base_url()}/api/v3/managed/blueprints/?page_size=100",
        headers=headers,
        timeout=10,
    )
    response.raise_for_status()
    return {
        blueprint["pk"]: (blueprint["name"], blueprint["status"])
        for blueprint in response.json().get("results", [])
        if not blueprint["name"].startswith(("System", "Default", "Migration"))
    }


def retry_call(call: Callable[[], dict], attempts: int, description: str) -> dict:
    """Retry a read operation so container health does not imply API readiness."""
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            return call()
        except Exception as error:
            last_error = error
            if attempt < attempts:
                time.sleep(POLL_INTERVAL)
    raise RuntimeError(f"{description} did not become available after {attempts} attempts") from last_error


def wait_for_apply_result(headers: dict, blueprint_pk: str, blueprint_name: str) -> bool:
    """Wait for one submitted apply to finish before another apply is submitted."""
    for _ in range(APPLY_STATUS_ATTEMPTS):
        blueprints = retry_call(
            lambda: get_custom_blueprints(headers),
            API_ATTEMPTS,
            "Authentik blueprint API",
        )
        blueprint = blueprints.get(blueprint_pk)
        if blueprint and blueprint[1] == "successful":
            return True
        time.sleep(POLL_INTERVAL)

    print(f'   -> Blueprint "{blueprint_name}" did not succeed before the apply timeout.')
    return False


def apply_sequentially(headers: dict, errored: list[tuple[str, str]]) -> None:
    """Recover errored blueprints without overlapping Authentik worker tasks."""
    if not errored:
        return

    print(f"   -> Retrying {len(errored)} errored blueprint(s) sequentially: {[n for _, n in errored]}")
    for blueprint_pk, blueprint_name in errored:
        succeeded = False
        for attempt in range(1, APPLY_ATTEMPTS + 1):
            response = request_json(
                "POST",
                f"{base_url()}/api/v3/managed/blueprints/{blueprint_pk}/apply/",
                headers=headers,
                timeout=10,
            )
            response.raise_for_status()
            if wait_for_apply_result(headers, blueprint_pk, blueprint_name):
                succeeded = True
                break
            if attempt < APPLY_ATTEMPTS:
                print(
                    f'   -> Retrying blueprint "{blueprint_name}" '
                    f"({attempt + 1}/{APPLY_ATTEMPTS})."
                )
                time.sleep(APPLY_RETRY_DELAY)
        if not succeeded:
            raise RuntimeError(
                f'blueprint "{blueprint_name}" failed after {APPLY_ATTEMPTS} serialized apply attempt(s)'
            )


def main() -> None:
    token = os.environ["AUTHENTIK_BOOTSTRAP_TOKEN"]
    headers = {"Authorization": f"Bearer {token}"}

    blueprints = retry_call(
        lambda: get_custom_blueprints(headers),
        API_ATTEMPTS,
        "Authentik blueprint API",
    )
    for _ in range(PASSIVE_ATTEMPTS):
        if blueprints and all(status == "successful" for _, status in blueprints.values()):
            print(f"   -> Custom blueprints ready ({len(blueprints)} custom blueprint(s) applied).")
            return
        if blueprints and all(status in ("successful", "error") for _, status in blueprints.values()):
            break
        time.sleep(POLL_INTERVAL)
        blueprints = retry_call(
            lambda: get_custom_blueprints(headers),
            API_ATTEMPTS,
            "Authentik blueprint API",
        )

    if not blueprints:
        raise RuntimeError("Authentik returned no custom blueprints")

    errored = sorted(
        ((pk, name) for pk, (name, status) in blueprints.items() if status == "error"),
        key=lambda item: item[1],
    )
    apply_sequentially(headers, errored)

    final = retry_call(
        lambda: get_custom_blueprints(headers),
        API_ATTEMPTS,
        "Authentik blueprint API",
    )
    still_broken = [name for name, status in final.values() if status != "successful"]
    if still_broken:
        raise RuntimeError(f"blueprints did not reach successful state: {still_broken}")
    print(f"   -> Custom blueprints ready ({len(final)} custom blueprint(s) applied).")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"   -> ERROR: Authentik blueprint provisioning failed: {error}", file=sys.stderr)
        sys.exit(1)
