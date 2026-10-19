#!/usr/bin/env python3
"""Regression tests for the repository language guard."""

import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).with_name("check_no_french.py")
SPEC = importlib.util.spec_from_file_location("check_no_french", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class NoFrenchCheckTests(unittest.TestCase):
    def test_reports_only_accented_lines(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            english = root / "english.md"
            french = root / "french.md"
            english.write_text("A plain English sentence.\n", encoding="utf-8")
            accented_line = "A line containing \u00e9."
            french.write_text(f"A plain line.\nUne phrase accentuee: securite.\n{accented_line}\n", encoding="utf-8")

            offenders = MODULE.find_accented_lines([english, french])

            self.assertEqual([(french, 3, accented_line)], offenders)

    def test_binary_extensions_are_case_insensitive(self):
        self.assertTrue(MODULE.is_binary_path("diagram.PNG"))
        self.assertFalse(MODULE.is_binary_path("README.md"))


if __name__ == "__main__":
    unittest.main()
