import json
import logging
import os
import subprocess
from typing import List, Optional
from presidio_analyzer import EntityRecognizer, RecognizerResult

logger = logging.getLogger("betterleaks_recognizer")


class BetterleaksRecognizer(EntityRecognizer):
    """
    Custom Presidio Recognizer that invokes the high-performance Betterleaks binary
    over stdin to detect technical secrets (API keys, tokens, SSH keys, credentials).
    """

    def __init__(
        self,
        binary_path: str = "/usr/local/bin/betterleaks",
        config_path: Optional[str] = None,
        supported_entities: Optional[List[str]] = None,
        supported_language: str = "en",
    ):
        self.binary_path = binary_path
        if config_path:
            self.config_path = config_path
        elif "BETTERLEAKS_CONFIG" in os.environ:
            self.config_path = os.environ["BETTERLEAKS_CONFIG"]
        else:
            local_config = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "config", "betterleaks.toml"
            )
            if os.path.exists(local_config):
                self.config_path = local_config
            else:
                self.config_path = "/etc/betterleaks/betterleaks.toml"
        super().__init__(
            supported_entities=supported_entities
            or [
                "SECRET",
                "API_KEY",
                "PRIVATE_KEY",
                "PASSWORD",
                "TOKEN",
                "CLOUD_CREDENTIAL",
            ],
            name=f"BetterleaksRecognizer_{supported_language}",
            supported_language=supported_language,
        )

    def load(self) -> None:
        """Verify betterleaks binary is available and dynamically load all rule IDs."""
        if not os.path.exists(self.binary_path):
            logger.warning(
                f"Betterleaks binary not found at {self.binary_path}, falling back to 'betterleaks'"
            )
            self.binary_path = "betterleaks"

        # Dynamically discover all supported rules from betterleaks config
        try:
            cmd = [self.binary_path, "config", "show"]
            if self.config_path and os.path.exists(self.config_path):
                cmd.extend(["-c", self.config_path])
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if proc.returncode == 0:
                import re
                rule_ids = re.findall(r"id\s*=\s*['\"]([^'\"]+)['\"]", proc.stdout)
                entity_set = set(self.supported_entities)
                for r_id in rule_ids:
                    entity_set.add(r_id.upper().replace("-", "_"))
                self.supported_entities = list(entity_set)
                logger.info(f"Betterleaks loaded {len(rule_ids)} rules into supported entities.")
        except Exception as e:
            logger.warning(f"Failed to dynamically query Betterleaks rule list: {e}")

    def analyze(
        self, text: str, entities: List[str], nlp_artifacts=None
    ) -> List[RecognizerResult]:
        if not text or not text.strip():
            return []

        cmd = [
            self.binary_path,
            "stdin",
            "--report-format",
            "json",
            "--report-path",
            "-",
            "--no-banner",
            "--log-level",
            "error",
            "--exit-code",
            "0",
        ]
        if self.config_path and os.path.exists(self.config_path):
            cmd.extend(["--config", self.config_path])

        try:
            proc = subprocess.run(
                cmd,
                input=text.encode("utf-8"),
                capture_output=True,
                timeout=10,
                check=False,
            )
            stdout = proc.stdout.decode("utf-8", errors="replace").strip()
            if not stdout:
                return []

            findings = json.loads(stdout)
            if not findings or not isinstance(findings, list):
                return []

            results = []

            # Precalculate line offsets in 0-indexed string
            lines = text.split("\n")
            line_starts = [0]
            for line in lines:
                line_starts.append(line_starts[-1] + len(line) + 1)

            for finding in findings:
                rule_id = finding.get("RuleID", "SECRET")
                start_line = finding.get("StartLine", 1) - 1
                end_line = finding.get("EndLine", 1) - 1
                start_col = finding.get("StartColumn", 1) - 1
                end_col = finding.get("EndColumn", 1)

                if 0 <= start_line < len(line_starts):
                    start_idx = line_starts[start_line] + start_col
                else:
                    start_idx = 0

                if 0 <= end_line < len(line_starts):
                    end_idx = line_starts[end_line] + end_col
                else:
                    end_idx = start_idx + len(finding.get("Secret", ""))

                start_idx = max(0, min(start_idx, len(text)))
                end_idx = max(start_idx, min(end_idx, len(text)))

                secret_val = finding.get("Secret")
                if secret_val and text[start_idx:end_idx] != secret_val:
                    pos = text.find(secret_val)
                    if pos != -1:
                        start_idx = pos
                        end_idx = pos + len(secret_val)

                # Format entity type cleanly (e.g. GITHUB_PAT, AWS_ACCESS_TOKEN)
                entity_name = rule_id.upper().replace("-", "_")

                if entities and "SECRET" not in entities and entity_name not in entities:
                    continue

                results.append(
                    RecognizerResult(
                        entity_type=entity_name,
                        start=start_idx,
                        end=end_idx,
                        score=1.0,
                        recognition_metadata={
                            "recognizer_name": "BetterleaksRecognizer",
                            "rule_id": rule_id,
                            "description": finding.get("Description", ""),
                        },
                    )
                )

            return results

        except Exception as e:
            logger.exception(f"Error executing Betterleaks analysis: {e}")
            return []
