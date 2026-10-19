"""Fail-closed checks for the Docker-backed staged Gitleaks hook."""

import os
from pathlib import Path
import secrets
import shutil
import string
import subprocess
import tempfile
import tomllib
import unittest


HOOK = Path(__file__).resolve().parents[1] / "git-hooks" / "pre-commit"
GITLEAKS_CONFIG = HOOK.parents[2] / ".gitleaks.toml"


class GitHookTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.base = Path(self.temp_dir.name)
        self.bin_dir = self.base / "bin"
        self.bin_dir.mkdir()
        self.repo_root = self.base / "worktree"
        self.repo_root.mkdir()
        self.common_dir = self.base / "common.git"
        self.common_dir.mkdir()
        self.args_file = self.base / "docker-args"

        git = self.bin_dir / "git"
        git.write_text(
            "#!/usr/bin/env bash\n"
            "case \"$*\" in\n"
            "  'rev-parse --show-toplevel') printf '%s\\n' \"$TEST_REPO_ROOT\" ;;\n"
            "  'rev-parse --path-format=absolute --git-common-dir') "
            "printf '%s\\n' \"$TEST_GIT_COMMON_DIR\" ;;\n"
            "  'diff --cached --quiet --') exit \"$TEST_DIFF_STATUS\" ;;\n"
            "  *) exit 2 ;;\n"
            "esac\n"
        )
        git.chmod(0o755)

        docker = self.bin_dir / "docker"
        docker.write_text(
            "#!/usr/bin/env bash\n"
            "printf '%s\\n' \"$@\" > \"$TEST_ARGS_FILE\"\n"
            "case \"$TEST_SCAN_RESULT\" in\n"
            "  clean) echo 'INF no leaks found' ;;\n"
            "  secret) echo 'WRN leaks found' >&2; exit 1 ;;\n"
            "  git_error) echo 'ERR [git] fatal: not a git repository' >&2 ;;\n"
            "  scanner_error) echo 'scanner failed' >&2; exit 2 ;;\n"
            "  *) exit 3 ;;\n"
            "esac\n"
        )
        docker.chmod(0o755)

    def run_hook(self, result="clean", diff_status="1", common_dir=None):
        env = os.environ.copy()
        env.update(
            PATH=f"{self.bin_dir}:/usr/bin:/bin",
            TEST_REPO_ROOT=str(self.repo_root),
            TEST_GIT_COMMON_DIR=str(common_dir or self.common_dir),
            TEST_DIFF_STATUS=diff_status,
            TEST_SCAN_RESULT=result,
            TEST_ARGS_FILE=str(self.args_file),
        )
        return subprocess.run(
            ["bash", str(HOOK)], cwd=self.repo_root, env=env,
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            check=False,
        )

    def test_clean_staged_change_in_linked_worktree(self):
        result = self.run_hook()
        self.assertEqual(result.returncode, 0, result.stdout)
        args = self.args_file.read_text().splitlines()
        self.assertIn("--network", args)
        self.assertIn("none", args)
        self.assertIn("--redact", args)
        self.assertIn("--pre-commit", args)
        self.assertIn("--staged", args)
        self.assertIn(
            f"type=bind,src={self.repo_root},dst={self.repo_root},readonly", args
        )
        self.assertIn(
            f"type=bind,src={self.common_dir},dst={self.common_dir},readonly", args
        )

    def test_clean_staged_change_in_main_worktree(self):
        common_dir = self.repo_root / ".git"
        common_dir.mkdir()
        result = self.run_hook(common_dir=common_dir)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_secret_blocks_commit(self):
        result = self.run_hook(result="secret")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("commit blocked", result.stdout)

    def test_silent_git_error_blocks_commit(self):
        result = self.run_hook(result="git_error")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("commit blocked", result.stdout)

    def test_scanner_failure_blocks_commit(self):
        result = self.run_hook(result="scanner_error")
        self.assertNotEqual(result.returncode, 0)

    def test_no_staged_changes_skips_scanner(self):
        result = self.run_hook(diff_status="0")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertFalse(self.args_file.exists())

    def test_git_diff_error_blocks_commit_without_scanning(self):
        result = self.run_hook(diff_status="128")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("commit blocked", result.stdout)
        self.assertFalse(self.args_file.exists())

    def test_default_detection_rules_remain_enabled(self):
        with GITLEAKS_CONFIG.open("rb") as config_file:
            config = tomllib.load(config_file)
        self.assertTrue(config["extend"]["useDefault"])


@unittest.skipUnless(
    os.environ.get("GITLEAKS_INTEGRATION") == "1", "requires Git and Docker"
)
class GitHookIntegrationTests(unittest.TestCase):
    def test_real_scanner_in_main_and_linked_worktrees(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            main = base / "main"
            linked = base / "linked"
            main.mkdir()
            subprocess.run(["git", "init", "-q", str(main)], check=True)
            subprocess.run(
                ["git", "config", "user.name", "Hook Test"], cwd=main, check=True
            )
            subprocess.run(
                ["git", "config", "user.email", "hook-test@example.invalid"],
                cwd=main, check=True,
            )
            shutil.copyfile(GITLEAKS_CONFIG, main / ".gitleaks.toml")
            subprocess.run(["git", "add", ".gitleaks.toml"], cwd=main, check=True)
            subprocess.run(
                ["git", "-c", "core.hooksPath=/dev/null", "commit", "-qm", "base"],
                cwd=main, check=True,
            )
            subprocess.run(
                ["git", "worktree", "add", "-qb", "linked", str(linked)],
                cwd=main, check=True,
            )

            for worktree in (main, linked):
                with self.subTest(worktree=worktree.name):
                    probe = worktree / "hook_probe.txt"
                    probe.write_text("This staged change is harmless.\n")
                    subprocess.run(["git", "add", "hook_probe.txt"], cwd=worktree, check=True)
                    clean = subprocess.run(
                        ["bash", str(HOOK)], cwd=worktree, text=True,
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
                    )
                    self.assertEqual(clean.returncode, 0, clean.stdout)
                    self.assertIn("no secrets detected", clean.stdout)

                    alphabet = string.ascii_letters + string.digits
                    fake_pat = "ghp_" + "".join(
                        secrets.choice(alphabet) for _ in range(36)
                    )
                    probe.write_text(f"synthetic_token={fake_pat}\n")
                    subprocess.run(["git", "add", "hook_probe.txt"], cwd=worktree, check=True)
                    blocked = subprocess.run(
                        ["bash", str(HOOK)], cwd=worktree, text=True,
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
                    )
                    self.assertNotEqual(blocked.returncode, 0, blocked.stdout)
                    self.assertIn("commit blocked", blocked.stdout)
                    self.assertNotIn(fake_pat, blocked.stdout)


if __name__ == "__main__":
    unittest.main()
