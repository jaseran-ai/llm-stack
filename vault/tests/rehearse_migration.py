#!/usr/bin/env python3
"""Exercise the legacy-to-RAM migration before a disposable UAT first start."""

import importlib.util
import os
from pathlib import Path
import secrets
import stat
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "vault" / "scripts" / "migrate_secrets.py"
SPEC = importlib.util.spec_from_file_location("vault_migrate_secrets", SCRIPT)
migration = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(migration)


def main():
    identity = ROOT / ".uat-identity"
    if not identity.is_file() or "ENVIRONMENT=uat" not in identity.read_text(encoding="utf-8").splitlines():
        raise RuntimeError("Migration rehearsal is limited to a disposable UAT worktree")
    values, _ = migration.read_env_metadata()
    identifier = values.get("SECRETS_RAM_ID")
    if not identifier:
        raise RuntimeError("UAT RAM metadata is missing")
    link = migration.LEGACY
    target = Path(f"{migration.provision.RAM_PREFIX}{identifier}")
    if not link.is_symlink() or os.readlink(link) != str(target):
        raise RuntimeError("UAT setup did not create the expected RAM link")
    if target.is_symlink() or (target.exists() and (not target.is_dir() or any(target.iterdir()))):
        raise RuntimeError("UAT RAM target is not an empty directory")
    if subprocess.run(["docker", "container", "ls", "--all", "--quiet"],
                      check=True, capture_output=True, text=True).stdout.strip():
        raise RuntimeError("UAT already contains application containers")
    if subprocess.run(["docker", "volume", "ls", "--quiet"],
                      check=True, capture_output=True, text=True).stdout.strip():
        raise RuntimeError("UAT already contains application volumes")

    link.unlink()
    link.mkdir(mode=0o777)
    marker = secrets.token_hex(16)
    (link / "vault_agent_token").write_text(marker, encoding="ascii")
    (link / "litellm.env").write_text("REHEARSAL_ONLY=1\n", encoding="ascii")
    migration.migrate()

    quarantine = link.with_name(f".secrets_ram.legacy-{identifier}")
    if not link.is_symlink() or not target.is_dir() or list(target.iterdir()):
        raise RuntimeError("Migration did not produce an empty private RAM directory")
    if stat.S_IMODE(quarantine.stat().st_mode) != 0o700:
        raise RuntimeError("Legacy quarantine is not private")
    if (quarantine / "vault_agent_token").read_text(encoding="ascii") != marker:
        raise RuntimeError("Legacy fixture was not preserved")
    print("[UAT] Legacy directory migrated to empty private tmpfs; fixture preserved in quarantine.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"[UAT] Migration rehearsal refused: {error}", file=sys.stderr)
        sys.exit(1)
