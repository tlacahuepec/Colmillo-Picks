#!/usr/bin/env python3
"""Release smoke tests for Colmillo-Picks.

Validates that release artifacts can execute basic operations without
requiring external API keys.

Usage:
    python scripts/smoke_test.py --cli
    python scripts/smoke_test.py --version-check
    python scripts/smoke_test.py --all

Exit codes:
    0 — all requested checks passed
    1 — one or more checks failed
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CLI_ENTRY_POINT = (
    REPO_ROOT / "skills" / "soccer-prop-picks" / "scripts" / "run_match_pick_pipeline.py"
)


def check_cli(entry_point: Path | None = None) -> bool:
    """Verify CLI can run in deterministic fallback mode."""
    target = entry_point or CLI_ENTRY_POINT

    if not target.exists():
        print(f"FAIL: CLI entry point not found: {target}")
        return False

    try:
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        result = subprocess.run(
            [
                sys.executable,
                str(target),
                "SmokeTest FC vs Verification United today",
                "--allow-deterministic-fallback",
            ],
            capture_output=True,
            text=True,
            timeout=45,
            cwd=str(REPO_ROOT),
            env=env,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired:
        print("FAIL: CLI timed out after 45 seconds")
        return False
    except FileNotFoundError:
        print(f"FAIL: Cannot execute {target}")
        return False

    if result.returncode != 0:
        print(f"FAIL: CLI exited with code {result.returncode}")
        if result.stderr:
            print(f"  stderr: {result.stderr[:500]}")
        return False

    if not result.stdout.strip():
        print("FAIL: CLI produced no output")
        return False

    print("PASS: CLI deterministic mode executed successfully")
    return True


def check_version() -> bool:
    """Verify app_metadata module can be imported and returns valid data."""
    app_metadata_path = REPO_ROOT / "skills" / "soccer-prop-picks" / "scripts" / "app_metadata.py"

    if not app_metadata_path.exists():
        print(f"FAIL: app_metadata.py not found at {app_metadata_path}")
        return False

    skills_path = str(REPO_ROOT / "skills" / "soccer-prop-picks")

    try:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                f"import sys; sys.path.insert(0, r'{skills_path}'); "
                "from scripts.app_metadata import get_app_metadata; "
                "m = get_app_metadata(); "
                "assert m.version, 'empty version'; "
                "assert m.channel in ('dev', 'rc', 'stable'), f'bad channel: {m.channel}'; "
                "print(f'version={m.version} channel={m.channel}')",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=str(REPO_ROOT),
        )
    except subprocess.TimeoutExpired:
        print("FAIL: Version check timed out")
        return False

    if result.returncode != 0:
        print("FAIL: Version check failed")
        if result.stderr:
            print(f"  stderr: {result.stderr[:500]}")
        return False

    print(f"PASS: Version check — {result.stdout.strip()}")
    return True


def main() -> int:
    args = sys.argv[1:]

    if not args:
        args = ["--all"]

    entry_point = None
    if "--entry-point" in args:
        idx = args.index("--entry-point")
        entry_point = Path(args[idx + 1])
        args = [a for i, a in enumerate(args) if i != idx and i != idx + 1]

    checks: list[tuple[str, bool]] = []

    if "--all" in args or "--cli" in args:
        checks.append(("cli", check_cli(entry_point)))

    if "--all" in args or "--version-check" in args:
        checks.append(("version", check_version()))

    if not checks:
        print("No checks specified. Use --cli, --version-check, or --all")
        return 1

    passed = sum(1 for _, ok in checks if ok)
    total = len(checks)
    print(f"\n{'='*40}")
    print(f"Smoke tests: {passed}/{total} passed")

    return 0 if all(ok for _, ok in checks) else 1


if __name__ == "__main__":
    sys.exit(main())
