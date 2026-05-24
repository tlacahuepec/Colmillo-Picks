"""Tests for scripts/package_cli.py — CLI release artifact packaging."""

from __future__ import annotations

import tarfile
from pathlib import Path

from scripts.package_cli import build_cli_archive, INCLUDE_PATTERNS, EXCLUDE_PATTERNS


REPO_ROOT = Path(__file__).resolve().parent.parent


class TestBuildCliArchive:
    def test_creates_tar_gz_archive(self, tmp_path: Path):
        output = tmp_path / "colmillo-cli.tar.gz"
        build_cli_archive(version="0.4.0", output_path=output)
        assert output.exists()
        assert output.stat().st_size > 0

    def test_archive_contains_cli_entry_point(self, tmp_path: Path):
        output = tmp_path / "colmillo-cli.tar.gz"
        build_cli_archive(version="0.4.0", output_path=output)
        with tarfile.open(output, "r:gz") as tar:
            names = tar.getnames()
        assert any("run_match_pick_pipeline.py" in n for n in names)

    def test_archive_contains_requirements(self, tmp_path: Path):
        output = tmp_path / "colmillo-cli.tar.gz"
        build_cli_archive(version="0.4.0", output_path=output)
        with tarfile.open(output, "r:gz") as tar:
            names = tar.getnames()
        assert any("requirements.txt" in n for n in names)

    def test_archive_contains_env_example(self, tmp_path: Path):
        output = tmp_path / "colmillo-cli.tar.gz"
        build_cli_archive(version="0.4.0", output_path=output)
        with tarfile.open(output, "r:gz") as tar:
            names = tar.getnames()
        assert any(".env.example" in n for n in names)

    def test_archive_contains_version_file(self, tmp_path: Path):
        output = tmp_path / "colmillo-cli.tar.gz"
        build_cli_archive(version="0.4.0", output_path=output)
        with tarfile.open(output, "r:gz") as tar:
            names = tar.getnames()
            assert any("VERSION" in n for n in names)
            version_member = next(m for m in tar.getmembers() if m.name.endswith("VERSION"))
            f = tar.extractfile(version_member)
            assert f is not None
            content = f.read().decode().strip()
            assert content == "0.4.0"

    def test_archive_excludes_env_file(self, tmp_path: Path):
        output = tmp_path / "colmillo-cli.tar.gz"
        build_cli_archive(version="0.4.0", output_path=output)
        with tarfile.open(output, "r:gz") as tar:
            names = tar.getnames()
        env_files = [n for n in names if n.endswith("/.env") or n == ".env"]
        assert env_files == []

    def test_archive_excludes_databases(self, tmp_path: Path):
        output = tmp_path / "colmillo-cli.tar.gz"
        build_cli_archive(version="0.4.0", output_path=output)
        with tarfile.open(output, "r:gz") as tar:
            names = tar.getnames()
        db_files = [n for n in names if n.endswith(".db") or n.endswith(".sqlite3")]
        assert db_files == []

    def test_archive_excludes_pycache(self, tmp_path: Path):
        output = tmp_path / "colmillo-cli.tar.gz"
        build_cli_archive(version="0.4.0", output_path=output)
        with tarfile.open(output, "r:gz") as tar:
            names = tar.getnames()
        cache_files = [n for n in names if "__pycache__" in n]
        assert cache_files == []

    def test_archive_excludes_git_directory(self, tmp_path: Path):
        output = tmp_path / "colmillo-cli.tar.gz"
        build_cli_archive(version="0.4.0", output_path=output)
        with tarfile.open(output, "r:gz") as tar:
            names = tar.getnames()
        git_files = [n for n in names if "/.git/" in n or n.startswith(".git/")]
        assert git_files == []

    def test_archive_excludes_tests(self, tmp_path: Path):
        output = tmp_path / "colmillo-cli.tar.gz"
        build_cli_archive(version="0.4.0", output_path=output)
        with tarfile.open(output, "r:gz") as tar:
            names = tar.getnames()
        test_files = [n for n in names if "/tests/" in n or n.startswith("tests/")]
        assert test_files == []

    def test_archive_top_level_directory_named_with_version(self, tmp_path: Path):
        output = tmp_path / "colmillo-cli.tar.gz"
        build_cli_archive(version="1.2.3", output_path=output)
        with tarfile.open(output, "r:gz") as tar:
            names = tar.getnames()
        assert all(n.startswith("colmillo-picks-1.2.3/") for n in names)

    def test_archive_contains_skills_scripts(self, tmp_path: Path):
        output = tmp_path / "colmillo-cli.tar.gz"
        build_cli_archive(version="0.4.0", output_path=output)
        with tarfile.open(output, "r:gz") as tar:
            names = tar.getnames()
        skills_files = [n for n in names if "skills/" in n and n.endswith(".py")]
        assert len(skills_files) > 0


class TestPatterns:
    def test_include_patterns_not_empty(self):
        assert len(INCLUDE_PATTERNS) > 0

    def test_exclude_patterns_covers_secrets(self):
        assert ".env" in EXCLUDE_PATTERNS or any(".env" in p for p in EXCLUDE_PATTERNS)
