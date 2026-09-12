import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_ruff_configuration_makes_the_ci_baseline_explicit() -> None:
    config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    ruff = config["tool"]["ruff"]
    lint = ruff["lint"]

    assert ruff["target-version"] == "py311"
    assert ruff["line-length"] == 100
    assert lint["select"] == ["E4", "E7", "E9", "F"]
    assert lint["ignore"] == ["E501"]


def test_ci_invokes_ruff_with_the_committed_configuration() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "run: ruff check ." in workflow
