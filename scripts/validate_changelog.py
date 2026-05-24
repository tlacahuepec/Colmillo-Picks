#!/usr/bin/env python3
"""Validate that CHANGELOG.md has an entry for a given version.

Usage:
    python scripts/validate_changelog.py v0.3.0
    python scripts/validate_changelog.py 0.4.0

Exit codes:
    0 — version section found
    1 — version section missing or malformed
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

CHANGELOG_PATH = Path(__file__).resolve().parent.parent / "CHANGELOG.md"

VERSION_HEADER_RE = re.compile(r"^## \[([^\]]+)\]")


def find_version_section(version: str, changelog_text: str) -> str | None:
    clean_version = version.lstrip("v")
    lines = changelog_text.splitlines()
    capture = False
    section_lines: list[str] = []

    for line in lines:
        match = VERSION_HEADER_RE.match(line)
        if match:
            if capture:
                break
            if match.group(1) == clean_version or match.group(1) == version:
                capture = True
                section_lines.append(line)
                continue
        if capture:
            section_lines.append(line)

    if not section_lines:
        return None

    content = "\n".join(section_lines).strip()
    if len(content.splitlines()) < 2:
        return None

    return content


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: validate_changelog.py <version>", file=sys.stderr)
        return 1

    version = sys.argv[1]

    if not CHANGELOG_PATH.exists():
        print(f"ERROR: {CHANGELOG_PATH} not found", file=sys.stderr)
        return 1

    changelog_text = CHANGELOG_PATH.read_text(encoding="utf-8")
    section = find_version_section(version, changelog_text)

    if section is None:
        print(f"ERROR: No changelog section found for version '{version}'", file=sys.stderr)
        print(f"Expected a heading like: ## [{version.lstrip('v')}]", file=sys.stderr)
        return 1

    print(f"OK: Found changelog section for {version}")
    print(f"---\n{section}\n---")
    return 0


if __name__ == "__main__":
    sys.exit(main())
