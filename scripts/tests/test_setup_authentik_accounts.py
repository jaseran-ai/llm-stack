"""Regression tests for the existing-deployment Authentik secret migration."""

import os
import pathlib
import shutil
import stat
import subprocess
import tempfile
import unittest


SETUP = pathlib.Path(__file__).parents[2] / "setup.sh"


class AuthentikAccountsSetupTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = pathlib.Path(self.directory.name)
        shutil.copy2(SETUP, self.root / "setup.sh")
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        for name, script in {
            "docker": "#!/bin/sh\nexit 0\n",
            "openssl": "#!/bin/sh\nprintf '%064d\\n' 0\n",
        }.items():
            path = bin_dir / name
            path.write_text(script)
            path.chmod(0o755)
        self.environment = os.environ.copy()
        self.environment["PATH"] = f"{bin_dir}:{self.environment['PATH']}"

    def run_setup(self, *args):
        return subprocess.run(
            ["bash", str(self.root / "setup.sh"), "--authentik-accounts-only", *args],
            cwd=self.root,
            env=self.environment,
            input="",
            text=True,
            capture_output=True,
            check=False,
        )

    def test_adds_only_missing_accounts_without_hydrating_templates(self):
        env_file = self.root / ".env"
        original = "DOMAIN=example.test\nUI_PASSWORD=preserved-admin\n"
        env_file.write_text(original)
        env_file.chmod(0o644)

        result = self.run_setup()

        self.assertEqual(result.returncode, 0, result.stderr)
        updated = env_file.read_text()
        self.assertTrue(updated.startswith(original))
        self.assertIn("ALICE_PASSWORD=", updated)
        self.assertIn("BOB_PASSWORD=", updated)
        self.assertEqual(updated.count("ALICE_PASSWORD="), 1)
        self.assertEqual(updated.count("BOB_PASSWORD="), 1)
        self.assertEqual(stat.S_IMODE(env_file.stat().st_mode), 0o600)
        backups = list(self.root.glob(".env.bak.*"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(), original)
        self.assertEqual(stat.S_IMODE(backups[0].stat().st_mode), 0o600)
        self.assertFalse((self.root / "authentik").exists())
        self.assertNotIn("preserved-admin", result.stdout)

        second = self.run_setup()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(env_file.read_text(), updated)
        self.assertEqual(len(list(self.root.glob(".env.bak.*"))), 1)

    def test_placeholder_is_rejected_before_any_account_is_added(self):
        env_file = self.root / ".env"
        original = "ALICE_PASSWORD=change_me\nUI_PASSWORD=preserved-admin\n"
        env_file.write_text(original)

        result = self.run_setup()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("refusing partial migration", result.stderr)
        self.assertEqual(env_file.read_text(), original)
        self.assertFalse(list(self.root.glob(".env.bak.*")))

    def test_requires_existing_env_and_rejects_force_regeneration(self):
        missing = self.run_setup()
        self.assertNotEqual(missing.returncode, 0)
        self.assertFalse((self.root / ".env").exists())

        (self.root / ".env").write_text("UI_PASSWORD=preserved-admin\n")
        forced = self.run_setup("--force-regen")
        self.assertNotEqual(forced.returncode, 0)
        self.assertEqual((self.root / ".env").read_text(), "UI_PASSWORD=preserved-admin\n")


if __name__ == "__main__":
    unittest.main()
