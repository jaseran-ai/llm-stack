"""Safety and isolated-restore tests for Langfuse logical snapshots."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "langfuse_snapshot.py"
SPEC = importlib.util.spec_from_file_location("langfuse_snapshot", SCRIPT)
SNAPSHOT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SNAPSHOT)
TEST_PASSPHRASE = secrets.token_hex(32).encode()


class LangfuseSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.base = Path(self.temp_dir.name)

    def test_private_working_directory_is_required(self):
        self.base.chmod(0o750)
        with self.assertRaisesRegex(SNAPSHOT.SnapshotError, "private"):
            SNAPSHOT.protected_directory(self.base)

    def test_symlinked_working_directory_is_rejected(self):
        link = self.base.parent / f"{self.base.name}-link"
        link.symlink_to(self.base)
        self.addCleanup(link.unlink)
        with self.assertRaisesRegex(SNAPSHOT.SnapshotError, "non-symlink"):
            SNAPSHOT.protected_directory(link)

    def test_working_directory_inside_git_is_rejected(self):
        git_result = subprocess.CompletedProcess([], 0, stdout="true\n")
        with mock.patch.object(SNAPSHOT.subprocess, "run", return_value=git_result):
            with self.assertRaisesRegex(SNAPSHOT.SnapshotError, "outside every Git"):
                SNAPSHOT.protected_directory(self.base)

    def test_short_passphrase_is_rejected(self):
        read_fd, write_fd = os.pipe()
        try:
            os.write(write_fd, b"too-short\n")
            os.close(write_fd)
            write_fd = None
            with self.assertRaisesRegex(SNAPSHOT.SnapshotError, "24 to 4096"):
                SNAPSHOT.read_passphrase(read_fd)
        finally:
            os.close(read_fd)
            if write_fd is not None:
                os.close(write_fd)

    def test_checksum_failure_precedes_decryption(self):
        archive = self.base / "langfuse-test.pgdump.gpg"
        archive.write_bytes(b"encrypted fixture")
        archive.chmod(0o600)
        manifest = Path(f"{archive}.json")
        manifest.write_text(json.dumps({
            "format": 1, "database": "langfuse", "archive": archive.name,
            "bytes": archive.stat().st_size, "sha256": "0" * 64,
        }))
        manifest.chmod(0o600)
        outside_git = subprocess.CompletedProcess([], 128, stdout="")
        with mock.patch.object(SNAPSHOT.subprocess, "run", return_value=outside_git), \
             mock.patch.object(SNAPSHOT, "start_gpg") as start_gpg:
            with self.assertRaisesRegex(SNAPSHOT.SnapshotError, "checksum"):
                SNAPSHOT.verify(archive, TEST_PASSPHRASE)
        start_gpg.assert_not_called()

    def test_existing_archive_is_not_deleted_on_name_collision(self):
        project = self.base / "project"
        project.mkdir()
        (project / "docker-compose.yml").write_text("services: {}\n")
        archive = self.base / "langfuse-fixed-deadbeef.pgdump.gpg"
        archive.write_bytes(b"pre-existing user data")
        with mock.patch.object(SNAPSHOT, "protected_directory", return_value=self.base), \
             mock.patch.object(
                 SNAPSHOT.subprocess, "run",
                 return_value=subprocess.CompletedProcess([], 0, stdout=b"1|1|1\n"),
             ), \
             mock.patch.object(SNAPSHOT, "datetime") as date, \
             mock.patch.object(SNAPSHOT.secrets, "token_hex", return_value="deadbeef"):
            date.now.return_value.strftime.return_value = "langfuse-fixed-"
            with self.assertRaises(FileExistsError):
                SNAPSHOT.snapshot(project, self.base, TEST_PASSPHRASE)
        self.assertEqual(archive.read_bytes(), b"pre-existing user data")


@unittest.skipUnless(
    os.environ.get("LANGFUSE_SNAPSHOT_INTEGRATION") == "1", "requires Docker and GnuPG"
)
class LangfuseSnapshotIntegrationTests(unittest.TestCase):
    def test_encrypted_archive_restores_in_isolated_postgres(self):
        fixture_command = """
set -eu
export PGDATA=/var/lib/postgresql/pgdata
initdb -D "$PGDATA" -A trust -U postgres --no-instructions >/dev/null
pg_ctl -D "$PGDATA" -o "-c listen_addresses= -c unix_socket_directories=/tmp" -l /tmp/pg.log -w start >/dev/null
createdb -h /tmp -U postgres langfuse
psql -h /tmp -U postgres -d langfuse -v ON_ERROR_STOP=1 -q -c \
  'CREATE TABLE users(id int); CREATE TABLE organizations(id int); CREATE TABLE projects(id int); INSERT INTO users VALUES (1); INSERT INTO organizations VALUES (1); INSERT INTO projects VALUES (1);' >/dev/null
pg_dump -h /tmp -U postgres -Fc langfuse
"""
        fixture = subprocess.run(
            [
                "docker", "run", "--rm", "--network", "none", "--read-only",
                "--user", "postgres", "--cap-drop", "ALL",
                "--security-opt", "no-new-privileges",
                "--tmpfs", "/var/lib/postgresql:rw,size=512m,mode=1777",
                "--tmpfs", "/tmp:rw,size=64m,mode=1777",
                "--entrypoint", "sh", SNAPSHOT.POSTGRES_IMAGE, "-ec", fixture_command,
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
        )
        self.assertTrue(fixture.stdout.startswith(b"PGDMP"))

        read_fd, write_fd = os.pipe()
        try:
            os.write(write_fd, TEST_PASSPHRASE + b"\n")
            os.close(write_fd)
            write_fd = None
            encrypted = subprocess.run(
                [
                    "gpg", "--batch", "--no-tty", "--pinentry-mode", "loopback",
                    "--no-symkey-cache", "--passphrase-fd", str(read_fd),
                    "--symmetric", "--cipher-algo", "AES256", "--output", "-",
                ], input=fixture.stdout, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, pass_fds=(read_fd,), check=True,
            ).stdout
        finally:
            os.close(read_fd)
            if write_fd is not None:
                os.close(write_fd)

        with tempfile.TemporaryDirectory() as temp_dir:
            project = Path(temp_dir) / "source"
            project.mkdir()
            (project / "docker-compose.yml").write_text("services: {}\n")
            fake_bin = Path(temp_dir) / "bin"
            fake_bin.mkdir()
            fake_docker = fake_bin / "docker"
            fake_docker.write_text(
                "#!/usr/bin/env python3\n"
                "import os, sys\n"
                "if sys.argv[1] == 'compose':\n"
                "    if 'psql' in sys.argv:\n"
                "        print('1|1|1')\n"
                "    else:\n"
                "        sys.stdout.buffer.write(bytes.fromhex(os.environ['SNAPSHOT_FIXTURE_HEX']))\n"
                "else:\n"
                "    os.execv('/usr/bin/docker', ['/usr/bin/docker', *sys.argv[1:]])\n"
            )
            fake_docker.chmod(0o755)
            with mock.patch.dict(os.environ, {
                "PATH": f"{fake_bin}:{os.environ['PATH']}",
                "SNAPSHOT_FIXTURE_HEX": fixture.stdout.hex(),
            }):
                exported, source_counts, restored_counts = SNAPSHOT.snapshot(
                    project, Path(temp_dir), TEST_PASSPHRASE
                )
            self.assertTrue(exported.is_file())
            self.assertEqual(source_counts, (1, 1, 1))
            self.assertEqual(restored_counts, (1, 1, 1))
            self.assertEqual(exported.stat().st_mode & 0o777, 0o600)
            self.assertEqual(SNAPSHOT.verify(exported, TEST_PASSPHRASE), (1, 1, 1))

            fake_docker.write_text(
                "#!/usr/bin/env python3\nimport sys\n"
                "if 'psql' in sys.argv:\n"
                "    print('1|1|1')\n"
                "else:\n"
                "    sys.exit(3)\n"
            )
            with mock.patch.dict(os.environ, {"PATH": f"{fake_bin}:{os.environ['PATH']}"}):
                with self.assertRaisesRegex(SNAPSHOT.SnapshotError, "pg_dump=3"):
                    SNAPSHOT.snapshot(project, Path(temp_dir), TEST_PASSPHRASE)
            self.assertEqual(list(Path(temp_dir).glob("langfuse-*.pgdump.gpg")), [exported])

            fake_docker.write_text(
                "#!/usr/bin/env python3\nimport os, sys\n"
                "if 'psql' in sys.argv:\n"
                "    print('2|1|1')\n"
                "elif sys.argv[1] == 'compose':\n"
                "    sys.stdout.buffer.write(bytes.fromhex(os.environ['SNAPSHOT_FIXTURE_HEX']))\n"
                "else:\n"
                "    os.execv('/usr/bin/docker', ['/usr/bin/docker', *sys.argv[1:]])\n"
            )
            with mock.patch.dict(os.environ, {
                "PATH": f"{fake_bin}:{os.environ['PATH']}",
                "SNAPSHOT_FIXTURE_HEX": fixture.stdout.hex(),
            }):
                with self.assertRaisesRegex(SNAPSHOT.SnapshotError, "row counts differ"):
                    SNAPSHOT.snapshot(project, Path(temp_dir), TEST_PASSPHRASE)
            self.assertEqual(list(Path(temp_dir).glob("langfuse-*.pgdump.gpg")), [exported])

            fake_docker.write_text(
                "#!/usr/bin/env python3\nimport os, sys\n"
                "if 'psql' in sys.argv:\n"
                "    print('1|1|1')\n"
                "else:\n"
                "    sys.stdout.buffer.write(bytes.fromhex(os.environ['SNAPSHOT_FIXTURE_HEX']))\n"
            )
            with mock.patch.dict(os.environ, {
                "PATH": f"{fake_bin}:{os.environ['PATH']}",
                "SNAPSHOT_FIXTURE_HEX": fixture.stdout.hex(),
            }), mock.patch.object(SNAPSHOT, "start_gpg", side_effect=FileNotFoundError("gpg unavailable")):
                with self.assertRaises(FileNotFoundError):
                    SNAPSHOT.snapshot(project, Path(temp_dir), TEST_PASSPHRASE)
            self.assertEqual(list(Path(temp_dir).glob("langfuse-*.pgdump.gpg")), [exported])

            archive = Path(temp_dir) / "langfuse-test.pgdump.gpg"
            archive.write_bytes(encrypted)
            archive.chmod(0o600)
            manifest = Path(f"{archive}.json")
            manifest.write_text(json.dumps({
                "format": 1, "database": "langfuse", "archive": archive.name,
                "bytes": len(encrypted), "sha256": hashlib.sha256(encrypted).hexdigest(),
            }))
            manifest.chmod(0o600)
            self.assertEqual(SNAPSHOT.verify(archive, TEST_PASSPHRASE), (1, 1, 1))
            with self.assertRaisesRegex(SNAPSHOT.SnapshotError, "restore failed"):
                SNAPSHOT.verify(archive, secrets.token_hex(32).encode())

            # Test rollback confirmation mismatch
            with self.assertRaisesRegex(SNAPSHOT.SnapshotError, "Confirmation mismatch"):
                SNAPSHOT.rollback(project, archive, "wrong-name.pgdump.gpg", TEST_PASSPHRASE)

            # Test rollback requires docker-compose.yml
            empty_dir = Path(temp_dir) / "empty-project"
            empty_dir.mkdir(mode=0o700)
            with mock.patch.object(SNAPSHOT, "verify", return_value=(1, 1, 1)):
                with self.assertRaisesRegex(SNAPSHOT.SnapshotError, "Target project has no docker-compose.yml"):
                    SNAPSHOT.rollback(empty_dir, archive, archive.name, TEST_PASSPHRASE)

    def test_rollback_stops_and_starts_writers(self):
        archive = self.base / "langfuse-test.pgdump.gpg"
        archive.write_bytes(b"dummy-encrypted-bytes")
        archive.chmod(0o600)
        manifest = Path(f"{archive}.json")
        manifest.write_text(json.dumps({
            "format": 1, "database": "langfuse", "archive": archive.name,
            "bytes": len(b"dummy-encrypted-bytes"), "sha256": hashlib.sha256(b"dummy-encrypted-bytes").hexdigest(),
        }))
        manifest.chmod(0o600)

        project = self.base / "project"
        project.mkdir(mode=0o700)
        (project / "docker-compose.yml").touch()

        run_calls = []

        def fake_run(cmd, *args, **kwargs):
            run_calls.append(cmd)
            if "count(*)" in str(cmd):
                return subprocess.CompletedProcess(cmd, 0, stdout=b"2|3|4\n", stderr=b"")
            return subprocess.CompletedProcess(cmd, 0, stdout=b"", stderr=b"")

        fake_decrypt = mock.Mock()
        fake_decrypt.stdout = mock.Mock()
        fake_decrypt.communicate.return_value = (b"", b"")
        fake_decrypt.returncode = 0
        fake_decrypt.poll.return_value = 0

        fake_restore = mock.Mock()
        fake_restore.communicate.return_value = (b"", b"")
        fake_restore.returncode = 0
        fake_restore.poll.return_value = 0

        with mock.patch.object(SNAPSHOT, "verify", return_value=(2, 3, 4)), \
             mock.patch.object(SNAPSHOT.subprocess, "run", side_effect=fake_run), \
             mock.patch.object(SNAPSHOT, "start_gpg", return_value=fake_decrypt), \
             mock.patch.object(SNAPSHOT.subprocess, "Popen", return_value=fake_restore):
            counts = SNAPSHOT.rollback(project, archive, archive.name, TEST_PASSPHRASE)

        self.assertEqual(counts, (2, 3, 4))
        # Ensure stop was called with writers
        stop_cmd = [c for c in run_calls if "stop" in c]
        self.assertEqual(len(stop_cmd), 1)
        self.assertIn("langfuse-web", stop_cmd[0])
        self.assertIn("langfuse-worker", stop_cmd[0])

        # Ensure start was called with writers
        start_cmd = [c for c in run_calls if "start" in c]
        self.assertEqual(len(start_cmd), 1)
        self.assertIn("langfuse-web", start_cmd[0])
        self.assertIn("langfuse-worker", start_cmd[0])

    def test_rollback_restarts_writers_on_restore_failure(self):
        archive = self.base / "langfuse-test.pgdump.gpg"
        archive.write_bytes(b"dummy-encrypted-bytes")
        archive.chmod(0o600)
        manifest = Path(f"{archive}.json")
        manifest.write_text(json.dumps({
            "format": 1, "database": "langfuse", "archive": archive.name,
            "bytes": len(b"dummy-encrypted-bytes"), "sha256": hashlib.sha256(b"dummy-encrypted-bytes").hexdigest(),
        }))
        manifest.chmod(0o600)

        project = self.base / "project"
        project.mkdir(mode=0o700)
        (project / "docker-compose.yml").touch()

        run_calls = []

        def fake_run(cmd, *args, **kwargs):
            run_calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 0, stdout=b"", stderr=b"")

        fake_decrypt = mock.Mock()
        fake_decrypt.stdout = mock.Mock()
        fake_decrypt.communicate.return_value = (b"", b"")
        fake_decrypt.returncode = 0
        fake_decrypt.poll.return_value = 0

        fake_restore = mock.Mock()
        fake_restore.communicate.return_value = (b"", b"database error")
        fake_restore.returncode = 1
        fake_restore.poll.return_value = 1

        with mock.patch.object(SNAPSHOT, "verify", return_value=(2, 3, 4)), \
             mock.patch.object(SNAPSHOT.subprocess, "run", side_effect=fake_run), \
             mock.patch.object(SNAPSHOT, "start_gpg", return_value=fake_decrypt), \
             mock.patch.object(SNAPSHOT.subprocess, "Popen", return_value=fake_restore):
            with self.assertRaisesRegex(SNAPSHOT.SnapshotError, "Live rollback pg_restore failed"):
                SNAPSHOT.rollback(project, archive, archive.name, TEST_PASSPHRASE)

        # Ensure start was still called despite error
        start_cmd = [c for c in run_calls if "start" in c]
        self.assertEqual(len(start_cmd), 1)
        self.assertIn("langfuse-web", start_cmd[0])
        self.assertIn("langfuse-worker", start_cmd[0])


if __name__ == "__main__":
    unittest.main()
