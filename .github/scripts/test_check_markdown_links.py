#!/usr/bin/env python3
"""Regression tests for the relative Markdown link validator."""

import importlib.util
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).with_name("check_markdown_links.py")
SPEC = importlib.util.spec_from_file_location("check_markdown_links", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class MarkdownLinkCheckTests(unittest.TestCase):
    def test_valid_broken_and_anchor_only_links(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "guide.md").write_text("# Guide\n", encoding="utf-8")
            (root / "README.md").write_text(
                "[valid](guide.md)\n"
                "[valid section](guide.md#usage)\n"
                "[same page](#usage)\n"
                "[external](https://example.com)\n"
                "[broken](missing.md)\n",
                encoding="utf-8",
            )

            broken = MODULE.find_broken_links(root, ignored_check=lambda _path: False)

            self.assertEqual([("README.md", "missing.md")], broken)

    def test_ignored_missing_link_is_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("[generated](runtime.yml)\n", encoding="utf-8")

            broken = MODULE.find_broken_links(root, ignored_check=lambda _path: True)

            self.assertEqual([], broken)


if __name__ == "__main__":
    unittest.main()
