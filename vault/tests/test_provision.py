#!/usr/bin/env python3
"""Unit tests for Vault provisioning and secret isolation."""

import importlib.util
import pathlib
import tempfile
import unittest
from unittest import mock

SCRIPT = pathlib.Path(__file__).parents[1] / "scripts" / "provision.py"
SPEC = importlib.util.spec_from_file_location("vault_provision", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class Response:
    """Minimal HTTP response used by the tests."""

    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self.payload = payload or {}
        self.text = text

    def json(self):
        return self.payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class VaultOidcTests(unittest.TestCase):
    """Validate CA handling and fail-closed OIDC configuration."""

    def test_oidc_requires_domain(self):
        with mock.patch.object(MODULE, "read_env", return_value={"TLS_MODE": "internal"}):
            with self.assertRaisesRegex(RuntimeError, "DOMAIN must be set in .env"):
                MODULE.setup_oidc("test-token")

    def test_internal_tls_requires_ca(self):
        with mock.patch.object(MODULE, "read_env", return_value={"TLS_MODE": "internal", "DOMAIN": "example.test"}), \
             mock.patch.object(MODULE.os.path, "exists", return_value=False), \
             mock.patch.object(MODULE.http_client, "get", return_value=Response(payload={"oidc/": {}})):
            with self.assertRaisesRegex(RuntimeError, "internal TLS requires"):
                MODULE.setup_oidc("test-token")

    def test_vault_rejection_is_fatal(self):
        fake_http = mock.Mock()
        fake_http.get.return_value = Response(payload={"oidc/": {}})
        fake_http.post.return_value = Response(status_code=400, text="discovery failed")
        with mock.patch.object(MODULE, "read_env", return_value={"TLS_MODE": "internal", "DOMAIN": "example.test"}), \
             mock.patch.object(MODULE.os.path, "exists", side_effect=lambda path: path == "traefik/certs/tls.crt"), \
             mock.patch("builtins.open", mock.mock_open(read_data="TEST CA")), \
             mock.patch.object(MODULE, "http_client", fake_http):
            with self.assertRaisesRegex(RuntimeError, "OIDC config failed"):
                MODULE.setup_oidc("test-token")

    def test_ca_is_sent_to_vault(self):
        fake_http = mock.Mock()
        fake_http.get.return_value = Response(payload={"oidc/": {}})
        fake_http.post.return_value = Response(status_code=204)
        with mock.patch.object(MODULE, "read_env", return_value={"TLS_MODE": "internal", "DOMAIN": "example.test"}), \
             mock.patch.object(MODULE.os.path, "exists", side_effect=lambda path: path == "traefik/certs/tls.crt"), \
             mock.patch("builtins.open", mock.mock_open(read_data="TEST CA")), \
             mock.patch.object(MODULE, "http_client", fake_http):
            MODULE.setup_oidc("test-token")

        config_payload = fake_http.post.call_args_list[0].kwargs["json"]
        self.assertEqual(config_payload["oidc_discovery_ca_pem"], "TEST CA")
        self.assertEqual(
            config_payload["oidc_discovery_url"],
            "https://authentik.example.test/application/o/vault/",
        )

    def test_skip_oidc_still_initializes_and_seeds(self):
        with mock.patch.object(MODULE, "init_and_unseal", return_value="test-token") as init, \
             mock.patch.object(MODULE, "seed_secrets") as seed, \
             mock.patch.object(MODULE, "configure_agent_approle") as approle, \
             mock.patch.object(MODULE, "setup_oidc") as setup:
            MODULE.main(["--skip-oidc"])

        init.assert_called_once_with()
        seed.assert_called_once_with("test-token")
        approle.assert_called_once_with("test-token")
        setup.assert_not_called()

    def test_oidc_only_uses_existing_root_token(self):
        with mock.patch.object(MODULE, "load_root_token", return_value="test-token") as load, \
             mock.patch.object(MODULE, "init_and_unseal") as init, \
             mock.patch.object(MODULE, "seed_secrets") as seed, \
             mock.patch.object(MODULE, "setup_oidc") as setup:
            MODULE.main(["--oidc-only"])

        load.assert_called_once_with()
        setup.assert_called_once_with("test-token")
        init.assert_not_called()
        seed.assert_not_called()

    def test_authentik_only_uses_existing_root_token_without_full_provisioning(self):
        with mock.patch.object(MODULE, "load_root_token", return_value="test-token") as load, \
             mock.patch.object(MODULE, "init_and_unseal") as init, \
             mock.patch.object(MODULE, "seed_secrets") as seed, \
             mock.patch.object(MODULE, "setup_oidc") as setup, \
             mock.patch.object(MODULE, "seed_authentik_accounts_only") as accounts:
            MODULE.main(["--authentik-accounts-only"])

        load.assert_called_once_with()
        accounts.assert_called_once_with("test-token")
        init.assert_not_called()
        seed.assert_not_called()
        setup.assert_not_called()

    def test_authentik_only_requires_existing_root_token(self):
        with mock.patch.object(MODULE, "load_root_token", return_value=""), \
             mock.patch.object(MODULE, "seed_authentik_accounts_only") as accounts:
            with self.assertRaises(SystemExit):
                MODULE.main(["--authentik-accounts-only"])

        accounts.assert_not_called()

    def test_authentik_only_rejects_missing_password_before_http(self):
        fake_http = mock.Mock()
        with mock.patch.object(MODULE, "read_env", return_value={"ALICE_PASSWORD": "generated-alice"}), \
             mock.patch.object(MODULE, "http_client", fake_http):
            with self.assertRaisesRegex(RuntimeError, "BOB_PASSWORD must be generated"):
                MODULE.seed_authentik_accounts_only("test-token")

        fake_http.get.assert_not_called()
        fake_http.post.assert_not_called()

    def test_authentik_only_writes_no_other_vault_secret(self):
        fake_http = mock.Mock()
        fake_http.get.return_value = Response(payload={"secret/": {"type": "kv", "options": {"version": "2"}}})
        fake_http.post.return_value = Response()
        passwords = {"ALICE_PASSWORD": "generated-alice", "BOB_PASSWORD": "generated-bob"}
        with mock.patch.object(MODULE, "read_env", return_value=passwords), \
             mock.patch.object(MODULE, "http_client", fake_http):
            MODULE.seed_authentik_accounts_only("test-token")

        fake_http.get.assert_called_once_with(
            f"{MODULE.VAULT_URL}/v1/sys/mounts", headers={"X-Vault-Token": "test-token"}
        )
        fake_http.post.assert_called_once_with(
            f"{MODULE.VAULT_URL}/v1/secret/data/llm-stack/authentik",
            headers={"X-Vault-Token": "test-token"}, json={"data": passwords},
        )

    def test_authentik_only_requires_existing_kv_v2_mount(self):
        fake_http = mock.Mock()
        fake_http.get.return_value = Response(payload={"secret/": {"type": "kv", "options": {"version": "1"}}})
        passwords = {"ALICE_PASSWORD": "generated-alice", "BOB_PASSWORD": "generated-bob"}
        with mock.patch.object(MODULE, "read_env", return_value=passwords), \
             mock.patch.object(MODULE, "http_client", fake_http):
            with self.assertRaisesRegex(RuntimeError, "existing KV v2"):
                MODULE.seed_authentik_accounts_only("test-token")

        fake_http.post.assert_not_called()

    def test_authentik_only_rejects_vault_write_error(self):
        fake_http = mock.Mock()
        fake_http.get.return_value = Response(payload={"secret/": {"type": "kv", "options": {"version": "2"}}})
        fake_http.post.return_value = Response(status_code=403)
        passwords = {"ALICE_PASSWORD": "generated-alice", "BOB_PASSWORD": "generated-bob"}
        with mock.patch.object(MODULE, "read_env", return_value=passwords), \
             mock.patch.object(MODULE, "http_client", fake_http):
            with self.assertRaisesRegex(RuntimeError, "HTTP 403"):
                MODULE.seed_authentik_accounts_only("test-token")

    def test_account_seeding_requires_both_generated_passwords(self):
        fake_http = mock.Mock()
        with mock.patch.object(MODULE, "read_env", return_value={"ALICE_PASSWORD": "generated-alice"}), \
             mock.patch.object(MODULE.http_client, "get", fake_http.get), \
             mock.patch.object(MODULE.http_client, "post", fake_http.post):
            with self.assertRaisesRegex(RuntimeError, "BOB_PASSWORD must be generated"):
                MODULE.seed_secrets("test-token")
        fake_http.get.assert_not_called()
        fake_http.post.assert_not_called()

    def test_account_seeding_writes_vault_kv_v2(self):
        fake_http = mock.Mock()
        fake_http.get.return_value = Response(payload={"secret/": {}})
        fake_http.post.return_value = mock.Mock(raise_for_status=mock.Mock())
        passwords = {"ALICE_PASSWORD": "generated-alice", "BOB_PASSWORD": "generated-bob"}
        with mock.patch.object(MODULE, "read_env", return_value=passwords), \
             mock.patch.object(MODULE.http_client, "get", fake_http.get), \
             mock.patch.object(MODULE.http_client, "post", fake_http.post), \
             mock.patch.object(MODULE.os, "makedirs"):
            MODULE.seed_secrets("test-token")

        auth_calls = [call for call in fake_http.post.call_args_list
                      if call.args[0].endswith("/secret/data/llm-stack/authentik")]
        self.assertEqual(len(auth_calls), 1)
        self.assertEqual(auth_calls[0].kwargs["json"], {"data": passwords})


class VaultAgentIsolationTests(unittest.TestCase):
    """Ensure Agent credentials are scoped and cannot spill to persistent disk."""

    def test_disk_directory_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            target = pathlib.Path(directory) / "target"
            target.mkdir()
            target.chmod(0o700)
            link = pathlib.Path(directory) / "secrets_ram"
            link.symlink_to(target)
            with mock.patch.object(MODULE, "SECRETS_DIRECTORY", str(link)), \
                 mock.patch.object(MODULE, "expected_ram_path", return_value=str(target)), \
                 mock.patch.dict(MODULE.os.environ, {"SECRETS_RAM_UID": str(MODULE.os.geteuid())}):
                with self.assertRaisesRegex(RuntimeError, "tmpfs"):
                    MODULE.require_ram_directory()

    def test_invalid_ram_id_is_rejected(self):
        with mock.patch.dict(MODULE.os.environ, {"SECRETS_RAM_ID": "validation-only"}):
            with self.assertRaisesRegex(RuntimeError, "16-character hex"):
                MODULE.expected_ram_path()

    def test_nonempty_legacy_directory_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            link = pathlib.Path(directory) / "secrets_ram"
            link.mkdir()
            marker = link / "existing-secret"
            marker.touch()
            with mock.patch.object(MODULE, "SECRETS_DIRECTORY", str(link)), \
                 mock.patch.object(MODULE, "expected_ram_path", return_value=str(pathlib.Path(directory) / "ram")):
                with self.assertRaisesRegex(RuntimeError, "nonempty"):
                    MODULE.prepare_ram_link()
            self.assertTrue(marker.exists())

    def test_wrong_ram_link_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            link = pathlib.Path(directory) / "secrets_ram"
            link.symlink_to(pathlib.Path(directory) / "wrong")
            with mock.patch.object(MODULE, "SECRETS_DIRECTORY", str(link)), \
                 mock.patch.object(MODULE, "expected_ram_path", return_value=str(pathlib.Path(directory) / "expected")):
                with self.assertRaisesRegex(RuntimeError, "private RAM path"):
                    MODULE.require_ram_link()

    @unittest.skipUnless(pathlib.Path("/dev/shm").is_dir(), "requires a Linux shared-memory mount")
    def test_ram_link_recreates_private_target_after_reboot(self):
        with tempfile.TemporaryDirectory(dir="/dev/shm") as directory:
            link = pathlib.Path(directory) / "secrets_ram"
            target = pathlib.Path(directory) / "ram"
            with mock.patch.object(MODULE, "SECRETS_DIRECTORY", str(link)), \
                 mock.patch.object(MODULE, "expected_ram_path", return_value=str(target)), \
                 mock.patch.dict(MODULE.os.environ, {"SECRETS_RAM_UID": str(MODULE.os.geteuid())}):
                MODULE.prepare_ram_link()
                MODULE.ensure_ram_directory()
                self.assertEqual(MODULE.require_ram_directory(), str(target))
                self.assertEqual(target.stat().st_mode & 0o777, 0o700)
                target.rmdir()
                MODULE.ensure_ram_directory()
                self.assertEqual(MODULE.require_ram_directory(), str(target))

    @unittest.skipUnless(pathlib.Path("/dev/shm").is_dir(), "requires a Linux shared-memory mount")
    def test_root_systemd_start_assigns_the_setup_owner(self):
        with tempfile.TemporaryDirectory(dir="/dev/shm") as directory:
            link = pathlib.Path(directory) / "secrets_ram"
            target = pathlib.Path(directory) / "ram"
            link.symlink_to(target)
            uid = MODULE.os.geteuid()
            gid = MODULE.os.getegid()
            with mock.patch.object(MODULE, "SECRETS_DIRECTORY", str(link)), \
                 mock.patch.object(MODULE, "expected_ram_path", return_value=str(target)), \
                 mock.patch.dict(MODULE.os.environ, {"SECRETS_RAM_UID": str(uid), "SECRETS_RAM_GID": str(gid)}), \
                 mock.patch.object(MODULE.os, "geteuid", return_value=0), \
                 mock.patch.object(MODULE.os, "chown") as chown:
                MODULE.ensure_ram_directory()
            chown.assert_called_once_with(str(target), uid, gid)

    def test_group_readable_directory_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            target = pathlib.Path(directory) / "target"
            target.mkdir()
            link = pathlib.Path(directory) / "secrets_ram"
            link.symlink_to(target)
            target.chmod(0o750)
            with mock.patch.object(MODULE, "SECRETS_DIRECTORY", str(link)), \
                 mock.patch.object(MODULE, "expected_ram_path", return_value=str(target)), \
                 mock.patch.dict(MODULE.os.environ, {"SECRETS_RAM_UID": str(MODULE.os.geteuid())}):
                with self.assertRaisesRegex(RuntimeError, "owner-only"):
                    MODULE.require_ram_directory()

    def test_legacy_root_token_is_rejected_before_http(self):
        with tempfile.TemporaryDirectory() as directory, \
             mock.patch.object(MODULE, "require_ram_directory", return_value=directory), \
             mock.patch.object(MODULE, "http_client") as client:
            (pathlib.Path(directory) / "vault_agent_token").touch()
            with self.assertRaisesRegex(RuntimeError, "Legacy root token"):
                MODULE.configure_agent_approle("root-token")
            client.put.assert_not_called()

    def test_approle_policy_is_read_only_and_credentials_are_not_root(self):
        with tempfile.TemporaryDirectory() as directory, \
             mock.patch.object(MODULE, "require_ram_directory", return_value=directory), \
             mock.patch.dict(MODULE.os.environ, {"SECRETS_RAM_UID": str(MODULE.os.geteuid()),
                                                  "SECRETS_RAM_GID": str(MODULE.os.getegid())}), \
             mock.patch.object(MODULE, "http_client") as client:
            client.put.return_value = Response()
            client.get.side_effect = [
                Response(payload={"approle/": {}}),
                Response(payload={"data": {"role_id": "role-only"}}),
            ]
            client.post.side_effect = [
                Response(),
                Response(payload={"data": {"secret_id": "secret-only"}}),
            ]
            MODULE.configure_agent_approle("root-token")

            policy = client.put.call_args.kwargs["json"]["policy"]
            self.assertIn('capabilities = ["read"]', policy)
            self.assertNotIn("root-token", policy)
            self.assertEqual((pathlib.Path(directory) / ".agent-role-id").read_text(), "role-only")
            self.assertEqual((pathlib.Path(directory) / ".agent-secret-id").read_text(), "secret-only")
            self.assertEqual((pathlib.Path(directory) / ".agent-secret-id").stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
