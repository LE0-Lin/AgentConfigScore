# User guide

English | [简体中文](simplified/user-guide.md) | [繁體中文](traditional/user-guide.md)

AgentConfigScore is a local, deterministic linter and PR regression gate for
coding-agent instruction files. It does not call an AI model, execute commands
from instruction files, or act as a filesystem sandbox. A score of 100 means no
active rule matched—not that the instructions are useful or safe in every
context.

To see how baseline-governed new-error gating differs from a plain score delta,
try the [regression design lab](../examples/regression-lab/README.md) from a
source checkout.

## 1. Install

Requires Python 3.10+. `diff` also requires Git; regular scans and `compare`
work without Git.

```bash
python -m pip install agent-config-score
agent-config-score --version
agent-config-score --help
```

You can also invoke the CLI via `acs` or `python -m agent_config_score` (handy
when the console script directory is not on `PATH`). Check
[releases](https://github.com/LE0-Lin/AgentConfigScore/releases) for what is
published on PyPI versus `main`.

## 2. Initialize a repository

```bash
agent-config-score init --dry-run
agent-config-score init
agent-config-score doctor
```

`init` creates `.agentconfigscore.json` and
`.github/workflows/agent-config-score.yml` without touching your instruction
files. Existing conflicting files are never overwritten unless you pass
`--force`; repeating an identical setup is a no-op. Review and commit the
generated files. If you only want local checks, use `init --no-workflow`.

Configuration rules to keep in mind:

- `.agentconfigscore.json` must be valid strict JSON (no duplicate keys,
  `NaN`/`Infinity`, or Boolean `version`) and resolve to a regular file inside
  the repository root. Missing config falls back to defaults; broken, dangling,
  or out-of-root config fails with exit `2` (`doctor` exits `1`).
- See [doctor and config boundaries](doctor.md#configuration-decoding) for
  details and migration steps.
- If `doctor` finds no supported instruction files, add repository-specific
  guidance or adapt one of the [templates](../examples/README.md). See
  [supported discovery](../README.md#what-it-scans).

## 3. Scan locally

```bash
agent-config-score .
agent-config-score rules
agent-config-score rules curl-pipe-shell
```

A plain scan prints findings and exits `0` by default. To enforce an absolute
score floor, set `fail_under` in `.agentconfigscore.json` or pass it on the
command line:

```bash
agent-config-score . --fail-under 90
```

You do not need a 90+ score to adopt the PR regression gate. Review findings by
rule, location, and context rather than treating the score as an overall quality
ranking.

## 4. Check changes before pushing

```bash
agent-config-score diff
```

`diff` compares your current working tree (including uncommitted edits) against
a locally available default branch without fetching. To specify a baseline ref
explicitly:

```bash
agent-config-score diff origin/main
```

In a shallow clone, fetch enough history first (the generated GitHub Actions
workflow uses `fetch-depth: 0`). Without Git, compare two directories directly:

```bash
agent-config-score compare ../repo-base . --max-drop 0 --fail-on-new-errors
```

Both sides are evaluated under the **baseline** policy and suppressions, so a
candidate PR cannot lower its own threshold or suppress its own new errors.
Moving an instruction file only avoids an `instruction-file-removed` error when
it is a one-to-one exact-text move to a newly added supported file in the same
directory (see [regression coverage](regression-coverage.md)).

## 5. Exit codes and resolving failures

- **Exit `1` (`diff` / `compare`)**: the regression gate failed. Fix the
  instruction change, or—if a finding is a deliberate exception—add a
  baseline-reviewed suppression with rule ID, reason, and expiry
  ([auditable exceptions](../README.md#auditable-exceptions)).
- **Exit `2`**: operational failure (bad config, missing Git ref, unreadable
  source, unwritable report). Never treat exit `2` as a passing check.

| Command | Exit 0 | Exit 1 | Exit 2 |
|---|---|---|---|
| Scan (`agent-config-score .`) | Scan completed; optional floor met | Score below configured floor | Invalid input or operational error |
| `diff`, `compare` | Baseline policy passed | New-error or score-drop gate failed | Comparison could not complete |
| `doctor` | No error checks (warnings allowed) | One or more error checks | Argument or invocation error |
| `scope` | Advisory analysis completed | Not used | Invalid input or read failure |
| `scope compare`, `scope diff`, `scope coverage` | Advisory completion or opted-in gate passed | Opted-in loss or unknown gate triggered | Invalid input, read failure, or limit hit |
| Other commands | Operation completed | Not used | Invalid input or operational error |

## 6. Save reports locally

```bash
agent-config-score . --json
agent-config-score . --html .agent-config-score/report.html --badge .agent-config-score/badge.svg --sarif .agent-config-score/results.sarif
agent-config-score diff --markdown .agent-config-score/regression.md
```

Write reports outside supported instruction paths so they are not scanned back
in. JSON, HTML, SARIF, and Markdown reports can include repository paths and
finding messages—inspect them before sharing. Each report also records the tool
version and source SHA-256 fingerprint ([report identity](report-identity.md)).

For local score snapshots, `history` fails with exit `2` on a damaged index
rather than silently resetting it ([local history](score-history-cli.md)).

To generate a privacy-minimized issue draft (nothing is uploaded):

```bash
agent-config-score feedback . --output .agent-config-score/case.md
```

## Optional: deletion safeguard review

```bash
agent-config-score guardrails . --file AGENTS.md
agent-config-score guardrails . --file AGENTS.md --template-language simplified --json
```

`guardrails` performs an unscored, single-file check for deletion-approval
wording without scanning the rest of the repository. By default it only previews
a suggested block. To append after reviewing the file, rerun with the printed
`--apply TOKEN` (which is bound to the exact file content). Example sections,
HTML markup, and opposing bypass phrases require manual editing; see
[guardrail suggestions](guardrail-suggestions.md).

## Optional: Cursor file-context and coverage analysis

```bash
agent-config-score scope . --target src/web/app.ts
agent-config-score scope . --target src/web/app.ts --target src/api/service.py --json
```

`scope` predicts automatic attachment for root `.cursor/rules/` files given
declared target paths (unscored; manual/model-selected rules stay `unknown`;
see [cursor-scope](cursor-scope.md) and the
[runnable example](../examples/cursor-scope/README.md)).

Compare the same declared context across changes, or check every regular file
under a directory independently:

```bash
agent-config-score scope compare ../repo-base . --target src/web/app.ts --fail-on-lost-directives --fail-on-unknown
agent-config-score scope diff origin/main --target src/web/app.ts --fail-on-lost-directives --fail-on-unknown --json
```

```bash
agent-config-score scope coverage --base-ref origin/main --under src --fail-on-lost-directives --fail-on-unknown --json
```

Without `--fail-on-*` flags these commands are advisory (exit `0`); with flags,
lost baseline-active directives or unknowns exit `1`. See
[cursor-scope-impact](cursor-scope-impact.md),
[cursor-coverage](cursor-coverage.md), and the
[four controls](../examples/cursor-scope-impact/README.md).

## Optional: `--explain` and PR comments

```bash
agent-config-score . --explain
agent-config-score diff --explain --markdown .agent-config-score/regression.md
agent-config-score init --pr-comment --dry-run
```

`--explain` adds static next-step guidance to text and Markdown output without
changing scores, JSON, or exit codes (see also the unscored
[best-practice checklist](best-practices.md)). `init --pr-comment` generates a
same-repository PR comment workflow with `pull-requests: write` (fork PRs still
use read-only job summaries). See [maintainer workflow](maintainer-workflow.md).

To upgrade only the CI workflow without touching `.agentconfigscore.json`:

```bash
agent-config-score init --workflow-only --pr-comment --force --dry-run
agent-config-score init --workflow-only --pr-comment --force
```

`--force` replaces the workflow file outright (it does not merge YAML); review
any custom edits first and run `doctor` separately to validate your policy.

## Troubleshooting

| Symptom | What to check |
|---|---|
| Command not found | Confirm the active Python environment's `Scripts`/`bin` directory is on `PATH`, or use `python -m agent_config_score`. |
| Config / workflow encoding error | Save the file as UTF-8, not UTF-16. |
| Cannot write HTML / SARIF / Markdown | Pass a writable file path, not an existing directory, and check parent permissions. |
| `Unable to read repository path index` | Run `doctor` and check the `repository-paths` error for unreadable directories. |
| Source resolution or read error | Check symlinks on instruction and ignore files; targets must be regular files inside the repo (`doctor` reports `instructions`). |
| `diff` cannot detect a baseline | Run `doctor`, then pass an available default-branch ref explicitly. |
| Prohibited command was flagged | Check [instruction-context.md](instruction-context.md) for the exact supported prohibition forms. |
| Old GitHub run is red | Check the run for the latest commit; later fixes do not clear earlier runs. |

Read [limitations.md](limitations.md) before relying on the tool as a CI gate.
