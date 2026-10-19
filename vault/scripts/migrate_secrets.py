#!/usr/bin/env python3
"""Explicit, fail-closed migration of a stopped legacy secret render directory."""

import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import stat
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
LEGACY = ROOT / "vault" / "secrets_ram"
ENV_FILE = ROOT / ".env"
PROVISION_FILE = Path(__file__).with_name("provision.py")
SPEC = importlib.util.spec_from_file_location("vault_provision", PROVISION_FILE)
provision = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(provision)

RAM_KEYS = ("SECRETS_RAM_UID", "SECRETS_RAM_GID", "SECRETS_RENDER_GID", "SECRETS_RAM_ID")


def read_env_metadata():
    """Read only migration metadata; never print the rest of the environment."""
    if not ENV_FILE.is_file() or ENV_FILE.is_symlink():
        raise RuntimeError("An existing, regular .env file is required")
    info = ENV_FILE.stat()
    if stat.S_IMODE(info.st_mode) & 0o077:
        raise RuntimeError(".env must be owner-only before migration")
    values = {}
    with ENV_FILE.open(encoding="utf-8") as source:
        for line in source:
            match = re.fullmatch(r"(SECRETS_RAM_UID|SECRETS_RAM_GID|SECRETS_RENDER_GID|SECRETS_RAM_ID)=(.*)\n?", line)
            if match:
                if match.group(1) in values:
                    raise RuntimeError("Duplicate RAM metadata in .env")
                values[match.group(1)] = match.group(2)
    for key in RAM_KEYS:
        if key in values and not re.fullmatch(r"[0-9]+" if key != "SECRETS_RAM_ID" else r"[0-9a-f]{16}", values[key]):
            raise RuntimeError(f"Invalid {key} in .env")
    if "SECRETS_RAM_UID" in values and int(values["SECRETS_RAM_UID"]) != info.st_uid:
        raise RuntimeError("SECRETS_RAM_UID must match the .env owner")
    if "SECRETS_RAM_GID" in values and int(values["SECRETS_RAM_GID"]) != info.st_gid:
        raise RuntimeError("SECRETS_RAM_GID must match the .env group")
    if "SECRETS_RENDER_GID" in values and values["SECRETS_RENDER_GID"] != "1000":
        raise RuntimeError("SECRETS_RENDER_GID must match the pinned SeaweedFS image")
    return values, info


def ensure_env_metadata():
    values, info = read_env_metadata()
    generated = {
        "SECRETS_RAM_UID": str(info.st_uid),
        "SECRETS_RAM_GID": str(info.st_gid),
        "SECRETS_RENDER_GID": "1000",
        "SECRETS_RAM_ID": secrets.token_hex(8),
    }
    missing = [key for key in RAM_KEYS if key not in values]
    if missing:
        # Append only migration metadata; never regenerate application credentials.
        with ENV_FILE.open("ab") as output:
            if ENV_FILE.stat().st_size and not ENV_FILE.read_bytes().endswith(b"\n"):
                output.write(b"\n")
            for key in missing:
                output.write(f"{key}={generated[key]}\n".encode("ascii"))
            output.flush()
            os.fsync(output.fileno())
        values, _ = read_env_metadata()
    return values


def running_bind_consumers(path):
    """Reject live direct mounts of the legacy directory or any contained file."""
    listed = subprocess.run(
        ["docker", "container", "ls", "--quiet", "--no-trunc"],
        check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    if not listed:
        return []
    inspected = subprocess.run(
        ["docker", "container", "inspect", *listed],
        check=True, capture_output=True, text=True,
    )
    affected = []
    for container in json.loads(inspected.stdout):
        for mount in container.get("Mounts", []):
            if mount.get("Type") != "bind":
                continue
            source = mount.get("Source", "")
            if source == str(path) or source.startswith(f"{path}/"):
                affected.append(container.get("Name", "unknown"))
                break
    return affected


def require_legacy_directory():
    if LEGACY.is_symlink() or not LEGACY.is_dir():
        raise RuntimeError("Expected an existing regular legacy secrets directory")
    if LEGACY.stat().st_dev != LEGACY.parent.stat().st_dev:
        raise RuntimeError("Legacy secret directory must not be a separate mount")
    for entry in LEGACY.iterdir():
        if not entry.is_file() or entry.is_symlink():
            raise RuntimeError("Legacy secret directory contains a non-regular entry")
    consumers = running_bind_consumers(LEGACY)
    if consumers:
        raise RuntimeError("Stop direct legacy bind consumers before migration: " + ", ".join(consumers))


def migrate():
    """Quarantine bytes on the original filesystem, then point renders to RAM."""
    require_legacy_directory()
    values = ensure_env_metadata()
    identifier = values["SECRETS_RAM_ID"]
    target = Path(f"{provision.RAM_PREFIX}{identifier}")
    quarantine = LEGACY.with_name(f".secrets_ram.legacy-{identifier}")
    if quarantine.exists() or quarantine.is_symlink() or target.is_symlink():
        raise RuntimeError("Migration quarantine or RAM target already exists")
    target_preexisting = target.exists()
    if target_preexisting and (not target.is_dir() or any(target.iterdir())):
        raise RuntimeError("RAM target must be an empty directory before migration")
    os.chmod(LEGACY, 0o700)
    try:
        # Check again after narrowing host access, immediately before the rename.
        consumers = running_bind_consumers(LEGACY)
        if consumers:
            raise RuntimeError("A legacy bind consumer appeared during migration")
        os.rename(LEGACY, quarantine)
        try:
            os.symlink(target, LEGACY)
            for key in RAM_KEYS:
                os.environ[key] = values[key]
            provision.SECRETS_DIRECTORY = str(LEGACY)
            provision.ensure_ram_directory()
        except Exception:
            if LEGACY.is_symlink():
                LEGACY.unlink()
            if not target_preexisting and target.is_dir() and not any(target.iterdir()):
                target.rmdir()
            os.rename(quarantine, LEGACY)
            raise
    except Exception:
        if LEGACY.is_dir() and not LEGACY.is_symlink():
            os.chmod(LEGACY, 0o700)
        raise
    print("[Vault] Legacy render files quarantined privately; RAM link prepared.")
    print(f"[Vault] Quarantine: {quarantine}")
    print("[Vault] No legacy credential was copied into RAM or deleted.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Migrate after every direct bind consumer is stopped")
    args = parser.parse_args(argv)
    try:
        if args.execute:
            migrate()
        else:
            require_legacy_directory()
            values, _ = read_env_metadata()
            print("[Vault] Preflight passed; no live direct bind consumer.")
            print(f"[Vault] RAM metadata present: {len(values)}/{len(RAM_KEYS)}")
            print("[Vault] No files were changed. Use --execute only after the approved cutover stop.")
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f"[Vault] Migration refused: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
