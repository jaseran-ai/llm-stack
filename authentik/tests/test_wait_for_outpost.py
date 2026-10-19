#!/usr/bin/env python3
"""Unit tests for Authentik outpost readiness probing and declarative blueprint."""

import importlib.util
import pathlib
import sys
import unittest
from unittest import mock

REPO_ROOT = pathlib.Path(__file__).parents[2]
SCRIPT = pathlib.Path(__file__).parents[1] / "scripts" / "wait_for_outpost.py"
sys.path.insert(0, str(SCRIPT.parent))
SPEC = importlib.util.spec_from_file_location("wait_for_outpost", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class Response:
    """Minimal requests response used by the tests."""

    def __init__(self, payload=None, status_code=200, headers=None):
        self.payload = payload
        self.status_code = status_code
        self.headers = headers or {}

    def json(self):
        return self.payload

    def raise_for_status(self) -> None:
        return None


class OutpostReadinessTests(unittest.TestCase):
    def test_forward_auth_retries_until_provider_is_ready(self) -> None:
        fake_client = mock.Mock()
        fake_client.side_effect = [
            Response(status_code=404),
            Response(
                status_code=302,
                headers={"Location": "https://authentik.example.test/application/o/authorize/"},
            ),
        ]

        with mock.patch.object(MODULE, "request_json", fake_client), mock.patch.object(
            MODULE.time, "sleep"
        ) as sleep, mock.patch.object(
            MODULE.time, "monotonic", side_effect=[0, 0]
        ), mock.patch.dict(
            MODULE.os.environ,
            {"AUTHENTIK_BASE_URL": "http://authentik-server:9000"},
            clear=True,
        ):
            MODULE.wait_for_forward_auth("example.test", timeout_seconds=2, retry_interval=2)

        self.assertEqual(fake_client.call_count, 2)
        sleep.assert_called_once_with(2)

    def test_forward_auth_timeout_is_fatal(self) -> None:
        fake_client = mock.Mock(return_value=Response(status_code=404))

        with mock.patch.object(MODULE, "request_json", fake_client), mock.patch.object(
            MODULE.time, "sleep"
        ) as sleep, mock.patch.object(
            MODULE.time, "monotonic", side_effect=[0, 0, 2]
        ), mock.patch.dict(
            MODULE.os.environ,
            {"AUTHENTIK_BASE_URL": "http://authentik-server:9000"},
            clear=True,
        ), self.assertRaisesRegex(RuntimeError, "did not become ready"):
            MODULE.wait_for_forward_auth("example.test", timeout_seconds=2, retry_interval=2)

        self.assertEqual(fake_client.call_count, 2)
        sleep.assert_called_once_with(2)

    def test_forward_auth_default_timeout_covers_cold_reconciliation(self) -> None:
        timeout_default = MODULE.wait_for_forward_auth.__defaults__[0]

        self.assertEqual(timeout_default, 600)

    def test_main_calls_wait_for_forward_auth(self) -> None:
        with mock.patch.dict(
            MODULE.os.environ,
            {"DOMAIN": "example.test", "AUTHENTIK_BASE_URL": "http://authentik-server:9000"},
            clear=True,
        ), mock.patch.object(MODULE, "wait_for_forward_auth") as wait_mock:
            MODULE.main()
            wait_mock.assert_called_once_with("example.test")

    def test_outpost_blueprint_contains_all_proxy_providers(self) -> None:
        """Verify that 10-forward-auth.yaml defines and binds all proxy providers."""
        import yaml

        class SafeLoaderIgnoreUnknown(yaml.SafeLoader):
            pass

        SafeLoaderIgnoreUnknown.add_multi_constructor(
            "", lambda loader, suffix, node: None
        )

        blueprint_path = REPO_ROOT / "authentik" / "blueprints" / "10-forward-auth.yaml"
        self.assertTrue(blueprint_path.is_file(), "10-forward-auth.yaml must exist")

        with open(blueprint_path) as f:
            data = yaml.load(f, Loader=SafeLoaderIgnoreUnknown) or {}

        provider_ids = set()
        for entry in data.get("entries", []):
            if entry and entry.get("model") == "authentik_providers_proxy.proxyprovider":
                provider_id = entry.get("id")
                if provider_id:
                    provider_ids.add(provider_id)

        self.assertEqual(len(provider_ids), 11, "Expected exactly 11 proxy providers in 10-forward-auth.yaml")

        blueprint_text = blueprint_path.read_text()
        for pid in provider_ids:
            self.assertIn(
                f"!KeyOf {pid}",
                blueprint_text,
                f"Proxy provider {pid} must be bound via !KeyOf in 10-forward-auth.yaml outpost",
            )


if __name__ == "__main__":
    unittest.main()
