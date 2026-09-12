import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_pyright_config_enforces_catalog_baseline() -> None:
    config = json.loads((ROOT / "pyrightconfig.json").read_text(encoding="utf-8"))

    assert config["pythonVersion"] == "3.11"
    assert config["typeCheckingMode"] == "basic"
    assert config["include"] == ["services/catalog"]


def test_ci_runs_pyright_after_installing_dev_dependencies() -> None:
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    dev_requirements = (ROOT / "requirements-dev.txt").read_text(encoding="utf-8")

    assert "pyright==1.1.414" in dev_requirements
    assert "name: Run Pyright" in workflow
    assert "run: pyright" in workflow
