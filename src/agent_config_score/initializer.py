from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import stat

from .config import SCHEMA_URL


class InitError(RuntimeError):
    """Raised when repository initialization cannot proceed safely."""


WORKFLOW_ACTION_REF = "LE0-Lin/AgentConfigScore@v0"


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


# Kept identical to examples/pr-comment.yml by an executable contract test.
# Embedded so installed wheels do not need the source checkout or network.
PR_COMMENT_WORKFLOW_CONTENT = r"""name: agent-config-regression

on:
  pull_request:

permissions:
  contents: read
  pull-requests: write

concurrency:
  group: agent-config-comment-${{ github.event.pull_request.number }}
  cancel-in-progress: true

jobs:
  regression:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
        with:
          fetch-depth: 0
          persist-credentials: false

      - uses: LE0-Lin/AgentConfigScore@v0
        id: acs

      - name: Create or update score comment
        if: >-
          ${{ !cancelled() && steps.acs.outputs.head-score != '' &&
              github.event.pull_request.head.repo.full_name == github.repository }}
        continue-on-error: true
        uses: actions/github-script@373c709c69115d41ff229c7e5df9f8788daa9553 # v9
        env:
          ACS_BASE_SCORE: ${{ steps.acs.outputs.base-score }}
          ACS_HEAD_SCORE: ${{ steps.acs.outputs.head-score }}
          ACS_DELTA: ${{ steps.acs.outputs.delta }}
          ACS_NEW_FINDINGS: ${{ steps.acs.outputs.new-findings }}
          ACS_NEW_ERRORS: ${{ steps.acs.outputs.new-errors }}
          ACS_RESOLVED: ${{ steps.acs.outputs.resolved-findings }}
          ACS_OUTCOME: ${{ steps.acs.outcome }}
        with:
          script: |
            const integer = (name, min, max = Number.MAX_SAFE_INTEGER) => {
              const raw = process.env[name] || '';
              if (!/^-?\d+$/.test(raw)) throw new Error(`Invalid ${name}`);
              const value = Number(raw);
              if (!Number.isSafeInteger(value) || value < min || value > max) {
                throw new Error(`Out-of-range ${name}`);
              }
              return value;
            };
            const base = integer('ACS_BASE_SCORE', 0, 100);
            const head = integer('ACS_HEAD_SCORE', 0, 100);
            const delta = integer('ACS_DELTA', -100, 100);
            const added = integer('ACS_NEW_FINDINGS', 0);
            const errors = integer('ACS_NEW_ERRORS', 0);
            const resolved = integer('ACS_RESOLVED', 0);
            if (delta !== head - base || errors > added) {
              throw new Error('Inconsistent AgentConfigScore outputs');
            }
            const outcome = process.env.ACS_OUTCOME;
            if (!['success', 'failure'].includes(outcome)) {
              throw new Error('Missing regression outcome');
            }
            const marker = '<!-- agent-config-score:regression -->';
            const runUrl = `${process.env.GITHUB_SERVER_URL}/${context.repo.owner}/${context.repo.repo}/actions/runs/${context.runId}`;
            const body = [
              marker,
              '### AgentConfigScore',
              '',
              `**${outcome === 'success' ? 'Passed' : 'Blocked'}** · Score: ${base} → ${head} (${delta > 0 ? '+' : ''}${delta})`,
              '',
              '| New findings | New errors | Resolved |',
              '|---:|---:|---:|',
              `| ${added} | ${errors} | ${resolved} |`,
              '',
              `[View findings and policy result](${runUrl})`,
              '',
              'The score covers detected rule matches; review individual findings.',
            ].join('\n');
            const comments = await github.paginate(github.rest.issues.listComments, {
              ...context.repo,
              issue_number: context.issue.number,
              per_page: 100,
            });
            const existing = comments.find(comment =>
              comment.user?.type === 'Bot' &&
              comment.user?.login === 'github-actions[bot]' &&
              comment.body?.startsWith(marker)
            );
            if (existing) {
              if (existing.body !== body) {
                await github.rest.issues.updateComment({
                  ...context.repo, comment_id: existing.id, body,
                });
              }
            } else {
              await github.rest.issues.createComment({
                ...context.repo, issue_number: context.issue.number, body,
              });
            }
"""


@dataclass(frozen=True)
class InitChange:
    path: Path
    action: str


def _targets(root: Path, include_config: bool, include_workflow: bool, pr_comment: bool) -> list[tuple[Path, str]]:
    items = [(root / ".agentconfigscore.json", CONFIG_CONTENT)] if include_config else []
    if include_workflow:
        content = PR_COMMENT_WORKFLOW_CONTENT if pr_comment else WORKFLOW_CONTENT
        items.append((root / ".github" / "workflows" / "agent-config-score.yml", content))
    return items


def _validate_target(root: Path, path: Path) -> None:
    """Reject known aliases/nonfiles before reading or writing selected targets.

    The explicitly selected root is canonicalized by the caller. These checks
    are not an atomic defense against arbitrary concurrent filesystem changes.
    """
    current = root
    for part in path.relative_to(root).parts:
        current = current / part
        try:
            info = current.lstat()
        except FileNotFoundError:
            continue
        except OSError as exc:
            raise InitError(f"could not inspect generated path: {current.relative_to(root)}") from exc
        if stat.S_ISLNK(info.st_mode) or (
            getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        ):
            raise InitError(f"refusing linked or reparse generated path: {current.relative_to(root)}")
        if current == path:
            if not stat.S_ISREG(info.st_mode):
                raise InitError(f"refusing non-file generated target: {path.relative_to(root)}")
            if info.st_nlink != 1 or info.st_ino == 0:
                raise InitError(f"refusing shared or unknown generated target: {path.relative_to(root)}")
        elif not stat.S_ISDIR(info.st_mode):
            raise InitError(f"generated parent is not a directory: {current.relative_to(root)}")


def _write_target(root: Path, path: Path, desired: str, action: str) -> None:
    descriptor = None
    try:
        _validate_target(root, path)
        path.parent.mkdir(parents=True, exist_ok=True)
        _validate_target(root, path)
        flags = os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0)
        if action == "create":
            flags |= os.O_CREAT | os.O_EXCL
        # Do not truncate until the opened object has been checked too.
        descriptor = os.open(path, flags, 0o666)
        opened = os.fstat(descriptor)
        _validate_target(root, path)
        named = path.lstat()
        if (not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1 or opened.st_ino == 0
                or (opened.st_dev, opened.st_ino) != (named.st_dev, named.st_ino)):
            raise InitError(f"generated target changed while opening: {path.relative_to(root)}")
        with os.fdopen(descriptor, "w", encoding="utf-8") as target:
            descriptor = None
            if action == "overwrite":
                target.truncate(0)
            target.write(desired)
    except OSError as exc:
        raise InitError(f"could not write generated target: {path.relative_to(root)}; inspect it before retrying") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def initialize_repository(
    root: Path,
    *,
    include_config: bool = True,
    include_workflow: bool = True,
    pr_comment: bool = False,
    force: bool = False,
    dry_run: bool = False,
) -> list[InitChange]:
    root = root.resolve()
    if not root.exists() or not root.is_dir():
        raise InitError(f"not a directory: {root}")

    if pr_comment and not include_workflow:
        raise InitError("PR comments require a workflow; do not combine --pr-comment with --no-workflow")
    if not include_config and not include_workflow:
        raise InitError("No initialization targets selected; do not combine --workflow-only with --no-workflow")
    targets = _targets(root, include_config, include_workflow, pr_comment)
    plan: list[tuple[Path, str, str]] = []

    # Preflight every target before writing anything. A conflicting workflow
    # must not leave a half-initialized policy file behind.
    for path, desired in targets:
        _validate_target(root, path)
        if not path.exists():
            plan.append((path, desired, "create"))
            continue
        if not path.is_file():
            raise InitError(f"refusing to replace non-file path: {path.relative_to(root)}")

        try:
            current = path.read_text(encoding="utf-8")
        except UnicodeError as exc:
            raise InitError(f"{path.relative_to(root)} must be saved as UTF-8") from exc
        except OSError as exc:
            raise InitError(f"could not read generated target: {path.relative_to(root)}") from exc

        if current == desired:
            plan.append((path, desired, "unchanged"))
        elif force:
            plan.append((path, desired, "overwrite"))
        else:
            hint = " Use --workflow-only for CI-only setup without resetting policy." if path.name == ".agentconfigscore.json" else ""
            raise InitError(
                f"refusing to overwrite existing {path.relative_to(root)}; "
                "review it or rerun with --force." + hint
            )

    if not dry_run:
        for path, desired, action in plan:
            if action == "unchanged":
                continue
            _write_target(root, path, desired, action)

    return [InitChange(path=path.relative_to(root), action=action) for path, _desired, action in plan]
