"""Unit and regression tests for declarative DNS modes in setup.sh."""

import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest


SETUP = pathlib.Path(__file__).parents[2] / "setup.sh"
COREFILE_TPL = pathlib.Path(__file__).parents[2] / "coredns" / "Corefile.template"


class SetupDnsModeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = pathlib.Path(self.directory.name)
        shutil.copy2(SETUP, self.root / "setup.sh")
        coredns_dir = self.root / "coredns"
        coredns_dir.mkdir()
        shutil.copy2(COREFILE_TPL, coredns_dir / "Corefile.template")

        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        for name, script in {
            "docker": "#!/bin/sh\nexit 0\n",
            "openssl": "#!/bin/sh\nprintf '%064d\\n' 0\n",
            "ip": "#!/bin/sh\necho '192.168.1.100'\n",
        }.items():
            path = bin_dir / name
            path.write_text(script)
            path.chmod(0o755)
        self.environment = os.environ.copy()
        self.environment["PATH"] = f"{bin_dir}:{self.environment['PATH']}"
        self.environment["REPO_DIR"] = str(self.root)

    def run_setup(self, *args):
        return subprocess.run(
            ["bash", str(self.root / "setup.sh"), *args],
            cwd=self.root,
            env=self.environment,
            input="",
            text=True,
            capture_output=True,
            check=False,
        )

    def test_invalid_dns_mode_fails_closed(self):
        result = self.run_setup("--dns-mode=invalid", "--domain=test.local")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Invalid --dns-mode", result.stderr)

    def test_corefile_hydration_substitutes_domain_and_ip(self):
        domain = "demo.stack.local"
        lan_ip = "192.168.1.50"
        escaped_domain = "demo\\.stack\\.local"

        tpl = (self.root / "coredns" / "Corefile.template").read_text()
        hydrated = (
            tpl.replace("${DOMAIN}", domain)
            .replace("${ESCAPED_DOMAIN}", escaped_domain)
            .replace("${LAN_IP}", lan_ip)
        )

        (self.root / "coredns" / "Corefile").write_text(hydrated)
        content = (self.root / "coredns" / "Corefile").read_text()
        self.assertIn("template IN A demo.stack.local", content)
        self.assertIn('match "(^|\\.)demo\\.stack\\.local\\.$"', content)
        self.assertIn("answer \"{{ .Name }} 60 IN A 192.168.1.50\"", content)
        self.assertIn("forward . 1.1.1.1 8.8.8.8", content)

    def test_existing_cloudflared_profile_is_preserved_as_cloudflare_mode(self):
        env_file = self.root / ".env"
        env_file.write_text("DOMAIN=preserved.ai\nCOMPOSE_PROFILES=cloudflared\n")

        # Mock python scripts called in setup.sh (vault, traefik)
        (self.root / "vault" / "scripts").mkdir(parents=True)
        (self.root / "vault" / "scripts" / "provision.py").write_text("import sys\nsys.exit(0)\n")
        (self.root / "traefik" / "scripts").mkdir(parents=True)
        (self.root / "traefik" / "scripts" / "hydrate_traefik.py").write_text("import sys\nsys.exit(0)\n")
        (self.root / "traefik" / "scripts" / "certs.sh").write_text("#!/bin/sh\nexit 0\n")
        (self.root / "prometheus").mkdir()
        (self.root / "prometheus" / "prometheus.yml.template").write_text("global:\n")
        (self.root / "litellm").mkdir()
        (self.root / "searxng").mkdir()
        (self.root / "searxng" / "settings.yml.template").write_text("use_default_settings: true\n")
        (self.root / "systemd").mkdir()
        (self.root / "systemd" / "llm-stack-langfuse-ingestion.service.template").write_text("")
        (self.root / "systemd" / "llm-stack-langfuse-ingestion.timer.template").write_text("")
        (self.root / "llm-stack.service.template").write_text("")

        result = self.run_setup()
        self.assertEqual(result.returncode, 0, result.stderr)
        env_content = env_file.read_text()
        self.assertIn("DNS_MODE=cloudflare", env_content)
        self.assertTrue((self.root / "coredns" / "Corefile").is_file())

    def test_explicit_dns_mode_coredns_sets_compose_profiles(self):
        env_file = self.root / ".env"
        env_file.write_text("DOMAIN=mytest.local\n")

        (self.root / "vault" / "scripts").mkdir(parents=True)
        (self.root / "vault" / "scripts" / "provision.py").write_text("import sys\nsys.exit(0)\n")
        (self.root / "traefik" / "scripts").mkdir(parents=True)
        (self.root / "traefik" / "scripts" / "hydrate_traefik.py").write_text("import sys\nsys.exit(0)\n")
        (self.root / "traefik" / "scripts" / "certs.sh").write_text("#!/bin/sh\nexit 0\n")
        (self.root / "prometheus").mkdir()
        (self.root / "prometheus" / "prometheus.yml.template").write_text("global:\n")
        (self.root / "litellm").mkdir()
        (self.root / "searxng").mkdir()
        (self.root / "searxng" / "settings.yml.template").write_text("use_default_settings: true\n")
        (self.root / "systemd").mkdir()
        (self.root / "systemd" / "llm-stack-langfuse-ingestion.service.template").write_text("")
        (self.root / "systemd" / "llm-stack-langfuse-ingestion.timer.template").write_text("")
        (self.root / "llm-stack.service.template").write_text("")

        result = self.run_setup("--dns-mode=coredns")
        self.assertEqual(result.returncode, 0, result.stderr)
        env_content = env_file.read_text()
        self.assertIn("DNS_MODE=coredns", env_content)
        self.assertIn("COMPOSE_PROFILES=coredns", env_content)

    def test_explicit_dns_mode_hosts_sets_empty_compose_profiles(self):
        env_file = self.root / ".env"
        env_file.write_text("DOMAIN=mytest.local\nCOMPOSE_PROFILES=cloudflared\n")

        (self.root / "vault" / "scripts").mkdir(parents=True)
        (self.root / "vault" / "scripts" / "provision.py").write_text("import sys\nsys.exit(0)\n")
        (self.root / "traefik" / "scripts").mkdir(parents=True)
        (self.root / "traefik" / "scripts" / "hydrate_traefik.py").write_text("import sys\nsys.exit(0)\n")
        (self.root / "traefik" / "scripts" / "certs.sh").write_text("#!/bin/sh\nexit 0\n")
        (self.root / "prometheus").mkdir()
        (self.root / "prometheus" / "prometheus.yml.template").write_text("global:\n")
        (self.root / "litellm").mkdir()
        (self.root / "searxng").mkdir()
        (self.root / "searxng" / "settings.yml.template").write_text("use_default_settings: true\n")
        (self.root / "systemd").mkdir()
        (self.root / "systemd" / "llm-stack-langfuse-ingestion.service.template").write_text("")
        (self.root / "systemd" / "llm-stack-langfuse-ingestion.timer.template").write_text("")
        (self.root / "llm-stack.service.template").write_text("")

        result = self.run_setup("--dns-mode=hosts")
        self.assertEqual(result.returncode, 0, result.stderr)
        env_content = env_file.read_text()
        self.assertIn("DNS_MODE=hosts", env_content)
        self.assertIn("COMPOSE_PROFILES=", env_content)


if __name__ == "__main__":
    unittest.main()
