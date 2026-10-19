#!/usr/bin/env python3
"""
Sync user passwords in Authentik.
Authentik's blueprint engine preserves existing users' passwords when `state: present`
is evaluated against existing user records. This script ensures that the passwords for
standard accounts (admin, alice, bob) match the configured environment variables.
"""

import os
from http_client import request_json


def main() -> None:
    token = os.environ["AUTHENTIK_BOOTSTRAP_TOKEN"]
    base_url = os.environ["AUTHENTIK_BASE_URL"].rstrip("/")
    admin_password = os.environ["UI_PASSWORD"]
    alice_password = os.environ["ALICE_PASSWORD"]
    bob_password = os.environ["BOB_PASSWORD"]
    if not all((admin_password, alice_password, bob_password)):
        raise ValueError("UI_PASSWORD, ALICE_PASSWORD, and BOB_PASSWORD must be non-empty")
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    response = request_json(
        "GET",
        f"{base_url}/api/v3/core/users/?page_size=100",
        headers=headers,
        timeout=15,
    )
    response.raise_for_status()
    users = {user["username"]: user["pk"] for user in response.json().get("results", [])}

    passwords = {
        "admin": admin_password,
        "alice": alice_password,
        "bob": bob_password,
    }
    for username, password in passwords.items():
        user_id = users.get(username)
        if user_id:
            response = request_json(
                "POST",
                f"{base_url}/api/v3/core/users/{user_id}/set_password/",
                headers=headers,
                payload={"password": password},
                timeout=10,
            )
            response.raise_for_status()

    print("   -> User passwords synchronized.")


if __name__ == "__main__":
    main()
