#!/usr/bin/env python3
"""Package Colmillo-Picks CLI as a distributable tar.gz archive.

Usage:
    python scripts/package_cli.py 0.4.0
    python scripts/package_cli.py 0.4.0 --output dist/colmillo-cli-0.4.0.tar.gz

Creates a tar.gz archive containing all source files needed to run the CLI
pipeline in deterministic fallback mode. Excludes secrets, databases, caches,
tests, and development tooling.
"""

from __future__ import annotations

import fnmatch
import io
import sys
import tarfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

INCLUDE_PATTERNS: list[str] = [
    "skills/**/*.py",
    "services/**/*.py",
    "scripts/**/*.py",
    "requirements.txt",
    "requirements-dev.txt",
    ".env.example",
    "README.md",
    "CHANGELOG.md",
    "docs/**/*.md",
]

EXCLUDE_PATTERNS: list[str] = [
    ".env",
    "*.db",
    "*.db-journal",
    "*.sqlite",
    "*.sqlite3",
    "__pycache__",
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    "*.pyc",
    "*.pyo",
    "tests",
    "data",
    ".venv",
    "venv",
    "node_modules",
    ".idea",
    "*.log",
    "sample_*.md",
]


def _should_exclude(path: Path) -> bool:
    parts = path.parts
    name = path.name
    for pattern in EXCLUDE_PATTERNS:
        if fnmatch.fnmatch(name, pattern):
            return True
        if pattern in parts:
            return True
    return False


def _collect_files(repo_root: Path) -> list[Path]:
    collected: list[Path] = []
    for pattern in INCLUDE_PATTERNS:
        for match in repo_root.glob(pattern):
            if match.is_file() and not _should_exclude(match.relative_to(repo_root)):
                collected.append(match)
    return sorted(set(collected))


def build_cli_archive(
    *,
    version: str,
    output_path: Path,
    repo_root: Path | None = None,
) -> Path:
    """Build a tar.gz CLI release archive.

    Args:
        version: Semantic version string (e.g. "0.4.0").
        output_path: Where to write the archive.
        repo_root: Repository root directory. Defaults to auto-detected.

    Returns:
        Path to the created archive.
    """
    root = repo_root or REPO_ROOT
    prefix = f"colmillo-picks-{version}"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    files = _collect_files(root)

    with tarfile.open(output_path, "w:gz") as tar:
        version_data = version.encode("utf-8")
        info = tarfile.TarInfo(name=f"{prefix}/VERSION")
        info.size = len(version_data)
        tar.addfile(info, io.BytesIO(version_data))

        for file_path in files:
            rel = file_path.relative_to(root)
            arcname = f"{prefix}/{rel.as_posix()}"
            tar.add(file_path, arcname=arcname)

    return output_path


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: package_cli.py <version> [--output PATH]", file=sys.stderr)
        return 1

    version = sys.argv[1].lstrip("v")

    output_path = Path(f"dist/colmillo-picks-{version}.tar.gz")
    if "--output" in sys.argv:
        idx = sys.argv.index("--output")
        if idx + 1 < len(sys.argv):
            output_path = Path(sys.argv[idx + 1])

    result = build_cli_archive(version=version, output_path=output_path)
    print(f"OK: Created {result} ({result.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
