# Dependency update policy

Dependabot checks Python packages, GitHub Actions, and root Dockerfiles every
Monday. Minor and patch updates are grouped by ecosystem to keep review volume
manageable; major upgrades remain individual pull requests so compatibility
changes are visible.

Security updates are never auto-merged. Every Dependabot pull request follows
the normal `dev` review flow and must pass CI: Ruff, Pyright, pytest, and the
container build where applicable. Update or close an obsolete Dependabot pull
request rather than bypassing CI.

The configuration intentionally covers only dependencies declared in this
repository. Runtime provider accounts, API keys, and external service versions
remain operational configuration rather than Dependabot-managed dependencies.

