from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .config import SCHEMA_URL


class InitError(RuntimeError):
    """Raised when repository initialization cannot proceed safely."""


CONFIG_CONTENT = f"""{{
  "$schema": "{SCHEMA_URL}",
  "version": 1,
  "policy": {{
    "max_drop": 0,
    "fail_on_new_errors": true
  }}
}}
"""

WORKFLOW_CONTENT = """name: agent-config-regression

on:
  pull_request:

permissions:
  contents: read

jobs:
  regression:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
        with:
          fetch-depth: 0
      - uses: LE0-Lin/AgentConfigScore@v0
"""


@dataclass(frozen=True)
class InitChange:
    path: Path
    action: str


def _targets(root: Path, include_workflow: bool) -> list[tuple[Path, str]]:
    items = [(root / ".agentconfigscore.json", CONFIG_CONTENT)]
    if include_workflow:
        items.append((root / ".github" / "workflows" / "agent-config-score.yml", WORKFLOW_CONTENT))
    return items


def initialize_repository(
    root: Path,
    *,
    include_workflow: bool = True,
    force: bool = False,
    dry_run: bool = False,
) -> list[InitChange]:
    root = root.resolve()
    if not root.exists() or not root.is_dir():
        raise InitError(f"not a directory: {root}")

    targets = _targets(root, include_workflow)
    plan: list[tuple[Path, str, str]] = []

    # Preflight every target before writing anything. A conflicting workflow
    # must not leave a half-initialized policy file behind.
    for path, desired in targets:
        if not path.exists():
            plan.append((path, desired, "create"))
            continue
        if not path.is_file():
            raise InitError(f"refusing to replace non-file path: {path.relative_to(root)}")

        try:
            current = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise InitError(f"could not read {path.relative_to(root)}: {exc}") from exc

        if current == desired:
            plan.append((path, desired, "unchanged"))
        elif force:
            plan.append((path, desired, "overwrite"))
        else:
            raise InitError(
                f"refusing to overwrite existing {path.relative_to(root)}; "
                "review it or rerun with --force"
            )

    if not dry_run:
        for path, desired, action in plan:
            if action == "unchanged":
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            try:
                path.write_text(desired, encoding="utf-8")
            except OSError as exc:
                raise InitError(f"could not write {path.relative_to(root)}: {exc}") from exc

    return [InitChange(path=path.relative_to(root), action=action) for path, _desired, action in plan]
