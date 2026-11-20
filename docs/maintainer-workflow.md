# Maintainer workflow: findings, next steps, and PR comments

Use `--explain`, `init --pr-comment`, and `init --workflow-only` (or the
copy-ready [pr-comment.yml](../examples/pr-comment.yml) recipe) to surface
actionable review guidance locally and on pull requests.

## 1. Inspect findings locally

```bash
agent-config-score . --explain
agent-config-score rules dead-path
agent-config-score rules prompt-injection-override
```

Each active finding includes its rule ID, severity, message, location, and a
static next step. `--explain` only changes text and Markdown presentation—it
does not modify files, execute commands, or alter scores, JSON, SARIF, HTML, or
exit codes. Suppressed/resolved findings and clean scans receive no extra
prompts. For general review guidance, see the unscored
[best-practice checklist](best-practices.md).

## 2. Review regressions against a baseline

```bash
agent-config-score diff --explain --markdown .agent-config-score/regression.md
```

Baseline policy and suppressions govern both sides. Next steps are attached only
to **new** findings so existing debt is not repeated on every PR.

In GitHub Actions, the composite Action writes explanatory Markdown to the job
summary automatically, and stays read-only unless your workflow opts into PR
comments. Optional PR comments show validated numeric results, a compact
rule/severity/count table (up to five rule types plus remaining count), local
recheck commands, and a link to the full report—never raw instruction text or
dynamic finding messages. When a gate passes with new warnings, the comment
still asks for review ([PR comment setup and compatibility](pr-comments.md)).

## 3. Enable a single PR comment

Preview first, then generate:

```bash
agent-config-score init --pr-comment --dry-run
agent-config-score init --pr-comment
```

Review and commit `.agentconfigscore.json` and
`.github/workflows/agent-config-score.yml`. The generated workflow matches
`examples/pr-comment.yml`:

- runs on `pull_request` (never `pull_request_target`) with `persist-credentials: false`;
- requests `pull-requests: write` only for same-repo PRs (fork PRs keep scanning and job summaries);
- updates one bot-owned comment instead of posting duplicates on every push;
- handles pagination, output validation, and comment-step failures without masking a failed regression gate.

Default `init` keeps GitHub permissions read-only. `--pr-comment` cannot be
combined with `--no-workflow`. Do not install a second workflow alongside an
existing comment recipe.

### Upgrade only the workflow

To update `.github/workflows/agent-config-score.yml` without touching
`.agentconfigscore.json`:

| Mode | Policy file | Workflow file |
|---|---|---|
| Default `init` | Generate / check | Generate / check |
| `init --no-workflow` | Generate / check | Untouched |
| `init --workflow-only` | Untouched | Generate / check |

```bash
agent-config-score init --workflow-only --pr-comment --force --dry-run
agent-config-score init --workflow-only --pr-comment --force
```

`--workflow-only` never reads, creates, or resets `.agentconfigscore.json`, even
with `--force`. Compare your existing workflow before passing `--force` (it
replaces the file rather than merging YAML), and run `doctor` separately to
validate your policy. Review or pin the generated `v0` Action ref as needed.

### Write boundaries

`init` refuses symlinks, Windows reparse points, hard-linked files, and non-file
targets for selected paths and their existing parent directories. Targets are
preflighted before writing, created exclusively when new, and keep existing
permissions on `--force` overwrite. Expected I/O failures exit `2`.

## Scope notes

Path, Markdown-link, and prompt-injection checks remain bounded deterministic
heuristics; see [limitations.md](limitations.md) for exact grammar boundaries.
