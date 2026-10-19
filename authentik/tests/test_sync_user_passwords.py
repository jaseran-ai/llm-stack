#!/usr/bin/env python3
"""Unit tests for strict Authentik password reconciliation."""

import importlib.util
import pathlib
import sys
import unittest
from unittest import mock

SCRIPT = pathlib.Path(__file__).parents[1] / "scripts" / "sync_user_passwords.py"
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("sync_user_passwords", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class Response:
    """Minimal successful HTTP response used by the tests."""

    def __init__(self, payload=None):
        self.payload = payload or {}

    def json(self):
        return self.payload

    def raise_for_status(self) -> None:
        return None


class PasswordSyncTests(unittest.TestCase):
    def test_required_environment_has_no_fallback(self) -> None:
        with mock.patch.dict(MODULE.os.environ, {}, clear=True), self.assertRaises(KeyError):
            MODULE.main()

    def test_all_configured_passwords_are_reconciled(self) -> None:
        fake_client = mock.Mock(
            side_effect=[
                Response({"results": [
                    {"username": "admin", "pk": 7},
                    {"username": "alice", "pk": 8},
                    {"username": "bob", "pk": 9},
                ]}),
                Response(),
                Response(),
                Response(),
            ]
        )
        environment = {
            "AUTHENTIK_BASE_URL": "http://authentik-server:9000/",
            "AUTHENTIK_BOOTSTRAP_TOKEN": "test-token",
            "UI_PASSWORD": "configured-password",
            "ALICE_PASSWORD": "configured-alice-password",
            "BOB_PASSWORD": "configured-bob-password",
        }
        with mock.patch.object(MODULE, "request_json", fake_client), mock.patch.dict(
            MODULE.os.environ, environment, clear=True
        ):
            MODULE.main()

        self.assertEqual(
            fake_client.call_args_list[0].args[1],
            "http://authentik-server:9000/api/v3/core/users/?page_size=100",
        )
        self.assertEqual(
            fake_client.call_args_list[1].kwargs["payload"],
            {"password": "configured-password"},
        )
        self.assertEqual(fake_client.call_args_list[2].kwargs["payload"], {"password": "configured-alice-password"})
        self.assertEqual(fake_client.call_args_list[3].kwargs["payload"], {"password": "configured-bob-password"})

    def test_missing_account_password_fails_before_api_calls(self) -> None:
        fake_client = mock.Mock()
        environment = {
            "AUTHENTIK_BASE_URL": "http://authentik-server:9000",
            "AUTHENTIK_BOOTSTRAP_TOKEN": "test-token",
            "UI_PASSWORD": "configured-password",
            "ALICE_PASSWORD": "configured-alice-password",
        }
        with mock.patch.object(MODULE, "request_json", fake_client), mock.patch.dict(
            MODULE.os.environ, environment, clear=True
        ), self.assertRaises(KeyError):
            MODULE.main()
        fake_client.assert_not_called()

    def test_empty_account_password_fails_before_api_calls(self) -> None:
        fake_client = mock.Mock()
        environment = {
            "AUTHENTIK_BASE_URL": "http://authentik-server:9000",
            "AUTHENTIK_BOOTSTRAP_TOKEN": "test-token",
            "UI_PASSWORD": "configured-password",
            "ALICE_PASSWORD": "configured-alice-password",
            "BOB_PASSWORD": "",
        }
        with mock.patch.object(MODULE, "request_json", fake_client), mock.patch.dict(
            MODULE.os.environ, environment, clear=True
        ), self.assertRaises(ValueError):
            MODULE.main()
        fake_client.assert_not_called()


if __name__ == "__main__":
    unittest.main()
