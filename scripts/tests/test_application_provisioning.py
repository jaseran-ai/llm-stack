#!/usr/bin/env python3
"""Tests for strict application OIDC provisioning and smoke-test credentials."""

import importlib.util
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

REPO_ROOT = pathlib.Path(__file__).parents[2]


def load_script(name, relative_path):
    script = REPO_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(name, script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


LITELLM = load_script("litellm_provision", "litellm/scripts/provision.py")


class Response:
    """Minimal successful HTTP response used by the provisioner tests."""

    def __init__(self, *, payload=None, headers=None, status_code=200, url=""):
        self.payload = payload or {}
        self.headers = headers or {}
        self.status_code = status_code
        self.url = url

    def json(self):
        return self.payload

    def raise_for_status(self):
        return None


class ProvisionerCredentialTests(unittest.TestCase):
    def test_litellm_requires_ui_password(self):
        with mock.patch.dict(LITELLM.os.environ, {"DOMAIN": "example.test"}, clear=True), \
             mock.patch.object(LITELLM, "Session") as session:
            with self.assertRaisesRegex(RuntimeError, "UI_PASSWORD must be set"):
                LITELLM.main()
        session.assert_not_called()

    def test_litellm_uses_configured_password_and_requires_success(self):
        session = mock.Mock()
        session.get.return_value = Response(headers={"Location": "https://issuer/authorize"})
        environment = {"DOMAIN": "example.test", "UI_PASSWORD": "configured-password"}
        with mock.patch.dict(LITELLM.os.environ, environment, clear=True), \
             mock.patch.object(LITELLM, "Session", return_value=session), \
             mock.patch.object(
                 LITELLM,
                 "oidc_authorize",
                 return_value=Response(url="https://litellm.example.test/ui/?login=success"),
             ) as authorize:
            LITELLM.main()

        self.assertEqual(authorize.call_args.args[3:], ("admin", "configured-password"))

        with mock.patch.dict(LITELLM.os.environ, environment, clear=True), \
             mock.patch.object(LITELLM, "Session", return_value=session), \
             mock.patch.object(
                 LITELLM,
                 "oidc_authorize",
                 return_value=Response(url="https://authentik.example.test/if/flow/login/"),
             ):
            with self.assertRaisesRegex(RuntimeError, "landed on"):
                LITELLM.main()

    def test_smoke_suite_requires_ui_password_without_fallback(self):
        environment = os.environ.copy()
        environment.pop("UI_PASSWORD", None)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        with tempfile.TemporaryDirectory() as working_directory:
            result = subprocess.run(
                [sys.executable, str(REPO_ROOT / "scripts/smoke_test.py"), "--list"],
                cwd=working_directory,
                env=environment,
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("UI_PASSWORD must be set", result.stderr)

    def test_smoke_suite_requires_account_passwords_without_fallback(self):
        environment = os.environ.copy()
        environment.pop("ALICE_PASSWORD", None)
        environment.pop("BOB_PASSWORD", None)
        environment["UI_PASSWORD"] = "configured-admin-password"
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        with tempfile.TemporaryDirectory() as working_directory:
            result = subprocess.run(
                [sys.executable, str(REPO_ROOT / "scripts/smoke_test.py"), "--list"],
                cwd=working_directory,
                env=environment,
                text=True,
                capture_output=True,
                check=False,
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ALICE_PASSWORD and BOB_PASSWORD must be set", result.stderr)


if __name__ == "__main__":
    unittest.main()
