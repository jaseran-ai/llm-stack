#!/usr/bin/env python3
"""Create and verify encrypted, database-scoped Langfuse rollback snapshots."""

import argparse
from datetime import datetime, timezone
import getpass
import hashlib
import json
import os
from pathlib import Path
import secrets
import stat
import subprocess
import sys


DATABASE = "langfuse"
POSTGRES_IMAGE = "postgres:18.6"
COUNT_QUERY = (
    "SELECT (SELECT count(*) FROM users), "
    "(SELECT count(*) FROM organizations), "
    "(SELECT count(*) FROM projects);"
)
RESTORE_COMMAND = """
set -eu
export PGDATA=/var/lib/postgresql/pgdata
initdb -D "$PGDATA" -A trust -U postgres --no-instructions >/dev/null
pg_ctl -D "$PGDATA" -o "-c listen_addresses= -c unix_socket_directories=/tmp" -l /tmp/pg.log -w start >/dev/null
createdb -h /tmp -U postgres langfuse
pg_restore -h /tmp -U postgres -d langfuse --single-transaction --exit-on-error --no-owner --no-acl
psql -h /tmp -U postgres -d langfuse -At -v ON_ERROR_STOP=1 -c \
  'SELECT (SELECT count(*) FROM users), (SELECT count(*) FROM organizations), (SELECT count(*) FROM projects);'
"""


class SnapshotError(Exception):
    """A safety check or external command failed."""


def protected_directory(value):
    path = Path(value).expanduser()
    if not path.is_absolute() or path.is_symlink() or not path.is_dir():
        raise SnapshotError("Working directory must be an existing absolute, non-symlink directory")
    path = path.resolve(strict=True)
    info = path.stat()
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise SnapshotError("Working directory must be owned by the caller and private (mode 0700)")
    git_check = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--is-inside-work-tree"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False, text=True,
    )
    if git_check.returncode == 0 and git_check.stdout.strip() == "true":
        raise SnapshotError("Working directory must be outside every Git worktree")
    return path


def protected_file(path):
    if path.is_symlink() or not path.is_file():
        raise SnapshotError("Snapshot and manifest must be regular, non-symlink files")
    info = path.stat()
    if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise SnapshotError("Snapshot and manifest must be owned by the caller and private (mode 0600)")


def read_passphrase(fd):
    if fd is None:
        value = getpass.getpass("Snapshot passphrase: ").encode("utf-8")
    else:
        value = os.read(fd, 4097).rstrip(b"\r\n")
    if not 24 <= len(value) <= 4096:
        raise SnapshotError("Passphrase must contain 24 to 4096 bytes; use a generated secret")
    if b"\n" in value or b"\r" in value:
        raise SnapshotError("Passphrase must be a single line")
    return value


def start_gpg(passphrase, operation, stdin, stdout):
    read_fd, write_fd = os.pipe()
    try:
        os.write(write_fd, passphrase + b"\n")
        os.close(write_fd)
        write_fd = None
        command = [
            "gpg", "--batch", "--no-tty", "--pinentry-mode", "loopback",
            "--no-symkey-cache", "--passphrase-fd", str(read_fd),
        ]
        if operation == "encrypt":
            command += ["--symmetric", "--cipher-algo", "AES256", "--output", "-"]
        else:
            command += ["--decrypt", "--output", "-"]
        return subprocess.Popen(
            command, stdin=stdin, stdout=stdout, stderr=subprocess.PIPE,
            pass_fds=(read_fd,),
        )
    finally:
        os.close(read_fd)
        if write_fd is not None:
            os.close(write_fd)


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_counts(output):
    counts = output.decode("utf-8", errors="replace").strip().split("|")
    if len(counts) != 3 or any(not count.isdigit() for count in counts):
        raise SnapshotError("Invalid Langfuse row counts")
    return tuple(int(count) for count in counts)


def snapshot(project_dir, output_dir, passphrase):
    output_dir = protected_directory(output_dir)
    project_dir = Path(project_dir).resolve(strict=True)
    compose_file = project_dir / "docker-compose.yml"
    if not compose_file.is_file():
        raise SnapshotError("Source project has no docker-compose.yml")
    name = datetime.now(timezone.utc).strftime("langfuse-%Y%m%dT%H%M%SZ-")
    archive = output_dir / f"{name}{secrets.token_hex(4)}.pgdump.gpg"
    manifest = Path(f"{archive}.json")
    compose = [
        "docker", "compose", "--project-name", "llm-stack",
        "--project-directory", str(project_dir), "-f", str(compose_file),
        "exec", "-T", "postgres",
    ]
    source = subprocess.run(
        compose + [
            "psql", "-U", "postgres", "-d", DATABASE, "-At",
            "-v", "ON_ERROR_STOP=1", "-c", COUNT_QUERY,
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if source.returncode:
        raise SnapshotError("Unable to read source Langfuse row counts")
    source_counts = parse_counts(source.stdout)
    command = compose + [
        "pg_dump", "-U", "postgres",
        "--format=custom", "--dbname=langfuse",
    ]
    created_archive = False
    created_manifest = False
    try:
        with os.fdopen(os.open(archive, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as output:
            created_archive = True
            with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as dump:
                crypt = None
                try:
                    crypt = start_gpg(passphrase, "encrypt", dump.stdout, output)
                    dump.stdout.close()
                    crypt.communicate()
                    dump.communicate()
                    if dump.returncode or crypt.returncode:
                        raise SnapshotError(
                            f"Snapshot failed (pg_dump={dump.returncode}, encryption={crypt.returncode}); "
                            "see service logs without printing database content"
                        )
                finally:
                    if crypt is not None and crypt.poll() is None:
                        crypt.kill()
                        crypt.wait()
                    if dump.poll() is None:
                        dump.kill()
            output.flush()
            os.fsync(output.fileno())
        data = {
            "format": 1, "database": DATABASE,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "archive": archive.name, "sha256": sha256_file(archive),
            "bytes": archive.stat().st_size,
        }
        with os.fdopen(os.open(manifest, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as handle:
            created_manifest = True
            json.dump(data, handle, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        restored_counts = verify(archive, passphrase)
        if restored_counts != source_counts:
            raise SnapshotError("Source and restored row counts differ; retry after concurrent writes stop")
        return archive, source_counts, restored_counts
    except Exception:
        if created_archive:
            archive.unlink(missing_ok=True)
        if created_manifest:
            manifest.unlink(missing_ok=True)
        raise


def verify(archive_path, passphrase):
    archive = Path(archive_path).expanduser()
    if not archive.is_absolute():
        raise SnapshotError("Archive path must be absolute")
    protected_directory(archive.parent)
    manifest = Path(f"{archive}.json")
    protected_file(archive)
    protected_file(manifest)
    with manifest.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if data.get("format") != 1 or data.get("database") != DATABASE or data.get("archive") != archive.name:
        raise SnapshotError("Manifest identity does not match a Langfuse snapshot")
    if data.get("bytes") != archive.stat().st_size or data.get("sha256") != sha256_file(archive):
        raise SnapshotError("Encrypted snapshot checksum or size mismatch")
    docker_command = [
        "docker", "run", "--rm", "--interactive", "--network", "none",
        "--read-only", "--user", "postgres", "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges", "--memory", "1g",
        "--tmpfs", "/var/lib/postgresql:rw,size=512m,mode=1777",
        "--tmpfs", "/tmp:rw,size=64m,mode=1777",
        "--entrypoint", "sh", POSTGRES_IMAGE, "-ec", RESTORE_COMMAND,
    ]
    with archive.open("rb") as encrypted:
        decrypt = start_gpg(passphrase, "decrypt", encrypted, subprocess.PIPE)
        restore = None
        try:
            restore = subprocess.Popen(
                docker_command, stdin=decrypt.stdout, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            decrypt.stdout.close()
            restore_output, _ = restore.communicate()
            decrypt.communicate()
        finally:
            if restore is not None and restore.poll() is None:
                restore.kill()
                restore.wait()
            if decrypt.poll() is None:
                decrypt.kill()
                decrypt.wait()
    if decrypt.returncode or restore.returncode:
        raise SnapshotError(
            f"Isolated restore failed (decryption={decrypt.returncode}, pg_restore={restore.returncode})"
        )
    return parse_counts(restore_output)


def rollback(project_dir, archive_path, confirm_name, passphrase):
    archive = Path(archive_path).expanduser()
    if not archive.is_absolute():
        raise SnapshotError("Archive path must be absolute")
    protected_directory(archive.parent)
    manifest = Path(f"{archive}.json")
    protected_file(archive)
    protected_file(manifest)

    if confirm_name != archive.name:
        raise SnapshotError(
            f"Confirmation mismatch: expected '{archive.name}', got '{confirm_name}'"
        )

    # 1. Preflight isolated verification: test manifest, checksums, and decrypt/restore in ephemeral tmpfs
    expected_counts = verify(archive, passphrase)

    project_dir = Path(project_dir).resolve(strict=True)
    compose_file = project_dir / "docker-compose.yml"
    if not compose_file.is_file():
        raise SnapshotError("Target project has no docker-compose.yml")

    compose_base = [
        "docker", "compose", "--project-name", "llm-stack",
        "--project-directory", str(project_dir), "-f", str(compose_file),
    ]

    # 2. Stop Langfuse writers to ensure clean database state during rollback
    stop_res = subprocess.run(
        compose_base + ["stop", "langfuse-web", "langfuse-worker"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if stop_res.returncode:
        raise SnapshotError("Failed to stop Langfuse consumers before rollback")

    try:
        # Terminate active backend connections to langfuse database
        terminate_query = (
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            f"WHERE datname = '{DATABASE}' AND pid <> pg_backend_pid();"
        )
        subprocess.run(
            compose_base + [
                "exec", "-T", "postgres",
                "psql", "-U", "postgres", "-d", "postgres", "-c", terminate_query,
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )

        # 3. Stream decrypted archive into live postgres container via pg_restore
        restore_cmd = compose_base + [
            "exec", "-T", "postgres",
            "pg_restore", "-U", "postgres", "-d", DATABASE,
            "--clean", "--if-exists", "--single-transaction",
            "--exit-on-error", "--no-owner", "--no-acl",
        ]
        with archive.open("rb") as encrypted:
            decrypt = start_gpg(passphrase, "decrypt", encrypted, subprocess.PIPE)
            restore = None
            try:
                restore = subprocess.Popen(
                    restore_cmd, stdin=decrypt.stdout, stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                decrypt.stdout.close()
                _, restore_err = restore.communicate()
                decrypt.communicate()
            finally:
                if restore is not None and restore.poll() is None:
                    restore.kill()
                    restore.wait()
                if decrypt.poll() is None:
                    decrypt.kill()
                    decrypt.wait()
        if decrypt.returncode or restore.returncode:
            err_msg = restore_err.decode("utf-8", errors="replace").strip() if restore_err else ""
            raise SnapshotError(
                f"Live rollback pg_restore failed (decryption={decrypt.returncode}, pg_restore={restore.returncode}): {err_msg}"
            )
    finally:
        # 4. Always restart stopped services
        start_res = subprocess.run(
            compose_base + ["start", "langfuse-web", "langfuse-worker"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
        )
        if start_res.returncode:
            raise SnapshotError("Failed to restart Langfuse consumers after rollback")

    # 5. Verify live row counts match the snapshot
    live = subprocess.run(
        compose_base + [
            "exec", "-T", "postgres",
            "psql", "-U", "postgres", "-d", DATABASE, "-At",
            "-v", "ON_ERROR_STOP=1", "-c", COUNT_QUERY,
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if live.returncode:
        raise SnapshotError("Unable to read post-rollback live Langfuse row counts")
    live_counts = parse_counts(live.stdout)
    if live_counts != expected_counts:
        raise SnapshotError(
            f"Post-rollback counts mismatch: expected {expected_counts}, got {live_counts}"
        )
    return live_counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--passphrase-fd", type=int, help="Read passphrase from an inherited file descriptor")
    actions = parser.add_subparsers(dest="action", required=True)
    export = actions.add_parser("snapshot", help="Take a read-only, encrypted production snapshot")
    export.add_argument("--project-dir", type=Path, required=True)
    export.add_argument("--output-dir", type=Path, required=True)
    check = actions.add_parser("verify", help="Restore an archive into isolated tmpfs PostgreSQL")
    check.add_argument("--archive", type=Path, required=True)
    roll = actions.add_parser("rollback", help="Safely roll back Langfuse database from an encrypted snapshot")
    roll.add_argument("--project-dir", type=Path, required=True)
    roll.add_argument("--archive", type=Path, required=True)
    roll.add_argument("--confirm", type=str, required=True, help="Confirm by typing the exact archive filename")
    args = parser.parse_args()
    os.umask(0o077)
    try:
        passphrase = read_passphrase(args.passphrase_fd)
        if args.action == "snapshot":
            archive, source_counts, restored_counts = snapshot(args.project_dir, args.output_dir, passphrase)
            print(f"Encrypted Langfuse snapshot: {archive}")
            print(f"SHA-256: {sha256_file(archive)}")
            print(
                "Source and isolated restore match: "
                f"users={restored_counts[0]}, organizations={restored_counts[1]}, "
                f"projects={restored_counts[2]}"
            )
        elif args.action == "rollback":
            counts = rollback(args.project_dir, args.archive, args.confirm, passphrase)
            print(f"Rollback successful: users={counts[0]}, organizations={counts[1]}, projects={counts[2]}")
        else:
            users, organizations, projects = verify(args.archive, passphrase)
            print(f"Isolated restore OK: users={users}, organizations={organizations}, projects={projects}")
    except (SnapshotError, OSError, subprocess.SubprocessError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
