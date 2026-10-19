#!/usr/bin/env python3
"""
Guard against accidentally reintroducing French text into this repository. The whole
codebase (documentation and scripts) was fully translated to English for its
international release - this check keeps it that way.

Binary files (images, PDFs, SQLite databases) are skipped automatically since they can
contain incidental byte sequences that look like accented UTF-8 characters.

Used by the CI workflow (.github/workflows/ci.yml) and can be run locally:
    python3 .github/scripts/check_no_french.py
"""
import subprocess
import sys
from pathlib import Path

ACCENTED_CHARS = "éèêëàâûôîçÉÈÊËÀÂÛÔÎÇ"
BINARY_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".svg", ".pdf", ".sqlite", ".ico", ".gif", ".webp",
}
# This script's own source is excluded.
SELF_PATH = Path(__file__).resolve()


def is_binary_path(path: str) -> bool:
    return any(path.lower().endswith(ext) for ext in BINARY_EXTENSIONS)


def find_text_files(root: Path):
    tracked = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=root,
        check=True,
        stdout=subprocess.PIPE,
    ).stdout.decode("utf-8").split("\0")
    for relative_path in tracked:
        if not relative_path:
            continue
        path = root / relative_path
        # A path scheduled for deletion remains in the index until the next commit.
        if not path.is_file():
            continue
        if is_binary_path(relative_path) or path.resolve() == SELF_PATH:
            continue
        # Official French translations and language switcher metadata for docs
        if "docs/" in relative_path and ("/i18n/fr/" in relative_path or "docusaurus.config.ts" in relative_path):
            continue
        yield path


def find_accented_lines(paths):
    """Return accented lines from readable UTF-8 text files."""
    offenders = []
    for path in paths:
        try:
            with open(path, encoding="utf-8") as fh:
                for lineno, line in enumerate(fh, start=1):
                    if any(ch in line for ch in ACCENTED_CHARS):
                        offenders.append((path, lineno, line.strip()))
        except (UnicodeDecodeError, FileNotFoundError):
            continue
    return offenders


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent.parent
    offenders = find_accented_lines(find_text_files(repo_root))

    if offenders:
        print(f"Found {len(offenders)} line(s) with French/accented characters:")
        for path, lineno, line in offenders:
            print(f"  {path}:{lineno}: {line[:120]}")
        return 1

    print("No French text found in any tracked file.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
