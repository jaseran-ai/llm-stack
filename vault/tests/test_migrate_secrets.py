#!/usr/bin/env python3
"""Regression tests for the explicit legacy render-directory migration."""

import importlib.util
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).parents[1] / "scripts" / "migrate_secrets.py"
SPEC = importlib.util.spec_from_file_location("vault_migrate_secrets", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
INSPECT_CONSUMERS = MODULE.running_bind_consumers


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.sandbox = tempfile.TemporaryDirectory()
        self.addCleanup(self.sandbox.cleanup)
        self.root = Path(self.sandbox.name)
        self.legacy = self.root / "vault" / "secrets_ram"
        self.legacy.mkdir(parents=True)
        self.legacy.chmod(0o777)
        (self.legacy / "vault_agent_token").write_text("fixture-root-token", encoding="utf-8")
        self.env = self.root / ".env"
        self.env.write_text("DOMAIN=example.test\nUI_PASSWORD=fixture-only\n", encoding="utf-8")
        self.env.chmod(0o600)
        self.ram = tempfile.TemporaryDirectory(dir="/dev/shm")
        self.addCleanup(self.ram.cleanup)
        self.patchers = [
            mock.patch.object(MODULE, "LEGACY", self.legacy),
            mock.patch.object(MODULE, "ENV_FILE", self.env),
            mock.patch.object(MODULE.provision, "RAM_PREFIX", f"{self.ram.name}/ram-"),
            mock.patch.object(MODULE.provision, "SECRETS_DIRECTORY", str(self.legacy)),
            mock.patch.object(MODULE, "running_bind_consumers", return_value=[]),
        ]
        for patcher in self.patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_migrates_without_copying_legacy_credentials_into_ram(self):
        MODULE.migrate()
        values, _ = MODULE.read_env_metadata()
        target = Path(f"{MODULE.provision.RAM_PREFIX}{values['SECRETS_RAM_ID']}")
        quarantine = self.legacy.with_name(f".secrets_ram.legacy-{values['SECRETS_RAM_ID']}")

        self.assertTrue(self.legacy.is_symlink())
        self.assertEqual(os.readlink(self.legacy), str(target))
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o700)
        self.assertEqual(stat.S_IMODE(quarantine.stat().st_mode), 0o700)
        self.assertEqual((quarantine / "vault_agent_token").read_text(), "fixture-root-token")
        self.assertEqual(list(target.iterdir()), [])
        self.assertEqual(self.env.read_text().count("UI_PASSWORD=fixture-only"), 1)
        self.assertEqual(len(values), 4)

    def test_running_direct_bind_blocks_every_change(self):
        with mock.patch.object(MODULE, "running_bind_consumers", return_value=["/vault-agent"]):
            with self.assertRaisesRegex(RuntimeError, "Stop direct legacy bind consumers"):
                MODULE.migrate()
        self.assertTrue(self.legacy.is_dir())
        self.assertFalse(self.legacy.is_symlink())
        self.assertEqual(self.env.read_text(), "DOMAIN=example.test\nUI_PASSWORD=fixture-only\n")

    def test_docker_mount_inspection_fails_closed(self):
        listed = mock.Mock(stdout="container-id\n")
        inspected = mock.Mock(stdout=json.dumps([{
            "Name": "/litellm",
            "Mounts": [{"Type": "bind", "Source": str(self.legacy / "litellm.env")}],
        }]))
        with mock.patch.object(MODULE.subprocess, "run", side_effect=[listed, inspected]):
            self.assertEqual(INSPECT_CONSUMERS(self.legacy), ["/litellm"])
        with mock.patch.object(MODULE.subprocess, "run", side_effect=OSError("daemon unavailable")):
            with self.assertRaisesRegex(OSError, "daemon unavailable"):
                INSPECT_CONSUMERS(self.legacy)

    def test_symlink_in_legacy_directory_is_rejected(self):
        (self.legacy / "unexpected").symlink_to(self.env)
        with self.assertRaisesRegex(RuntimeError, "non-regular"):
            MODULE.migrate()
        self.assertFalse(self.legacy.is_symlink())

    def test_existing_ram_target_is_never_overwritten(self):
        identifier = "a" * 16
        with self.env.open("a", encoding="utf-8") as output:
            output.write(f"SECRETS_RAM_ID={identifier}\n")
        target = Path(f"{MODULE.provision.RAM_PREFIX}{identifier}")
        target.mkdir()
        (target / "marker").touch()
        with self.assertRaisesRegex(RuntimeError, "empty directory"):
            MODULE.migrate()
        self.assertTrue((target / "marker").exists())
        self.assertFalse(self.legacy.is_symlink())

    def test_existing_empty_ram_mountpoint_is_accepted(self):
        identifier = "a" * 16
        with self.env.open("a", encoding="utf-8") as output:
            output.write(f"SECRETS_RAM_ID={identifier}\n")
        target = Path(f"{MODULE.provision.RAM_PREFIX}{identifier}")
        target.mkdir(mode=0o700)
        MODULE.migrate()
        self.assertTrue(target.is_dir())
        self.assertEqual(list(target.iterdir()), [])
        self.assertTrue(self.legacy.is_symlink())

    def test_wrong_filesystem_rolls_back_to_private_legacy_directory(self):
        with mock.patch.object(MODULE.provision, "ensure_ram_directory", side_effect=RuntimeError("not tmpfs")):
            with self.assertRaisesRegex(RuntimeError, "not tmpfs"):
                MODULE.migrate()
        self.assertTrue(self.legacy.is_dir())
        self.assertFalse(self.legacy.is_symlink())
        self.assertEqual(stat.S_IMODE(self.legacy.stat().st_mode), 0o700)
        self.assertEqual((self.legacy / "vault_agent_token").read_text(), "fixture-root-token")

    def test_duplicate_metadata_is_rejected(self):
        with self.env.open("a", encoding="utf-8") as output:
            output.write(f"SECRETS_RAM_ID={'a' * 16}\nSECRETS_RAM_ID={'b' * 16}\n")
        with self.assertRaisesRegex(RuntimeError, "Duplicate RAM metadata"):
            MODULE.migrate()
        self.assertFalse(self.legacy.is_symlink())


if __name__ == "__main__":
    unittest.main()
