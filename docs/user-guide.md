# User guide

English | [简体中文](zh-CN/user-guide.md) | [繁體中文](zh-TW/user-guide.md)

AgentConfigScore is a local, deterministic linter and pull-request regression
gate for coding-agent instructions. It does not call an AI service or execute
commands found in instruction files. A 100 means no active rule matched, not
that instructions are useful, safe in every context, or better than AI review.

## 1. Install and check the version

Python 3.10 or later is required. Git is required for `diff`, but not for a
normal directory scan or `compare` of two directories.

```bash
python -m pip install agent-config-score
agent-config-score --version
agent-config-score --help
```

`acs` is a shorter alias. Version 0.23.0 and later also support
`python -m agent_config_score` with the same product commands, without relying
on the console script's PATH setup. Older versions do not provide this module
entrypoint. Check [releases](https://github.com/LE0-Lin/AgentConfigScore/releases)
before assuming a change on `main` is available on PyPI or the rolling `v0` ref.

## 2. Initialize in your repository

```bash
agent-config-score init --dry-run
agent-config-score init
agent-config-score doctor
```

`init` creates `.agentconfigscore.json` and
`.github/workflows/agent-config-score.yml`. It does not create or rewrite your
instruction files. Existing conflicting files are not overwritten by default;
review them before using `--force`. A matching second initialization is a no-op.

Commit the generated files after reviewing them. If you only want local checks,
use `init --no-workflow`. A missing standard workflow is then an advisory doctor
warning, not an error.

If doctor finds no supported instruction files, add repository-specific
instructions or adapt one of the [templates](../examples/README.md). Do not add
phrases just to increase the score. See [supported discovery](../README.md#what-it-scans).

## 3. Inspect the current tree

```bash
agent-config-score .
agent-config-score rules
agent-config-score rules curl-pipe-shell
```

A normal scan reports findings without blocking by default. To require an
absolute score floor, use a policy `fail_under` or an explicit option:

```bash
agent-config-score . --fail-under 90
```

This distinction is intentional: an existing repository does not need to reach
90 before adopting a regression gate. Review each finding's rule, location and
context instead of treating the numeric score as a quality ranking.

## 4. Check the change before pushing

```bash
agent-config-score diff
```

This checks the current working tree, including uncommitted edits. It uses a
safe locally available default-branch baseline where possible and never fetches.
To choose the baseline explicitly:

```bash
agent-config-score diff origin/main
```

If `origin/main` is missing, fetch that branch yourself. Use the project's actual
default branch, not a feature branch that already contains the change. In a
shallow checkout, obtain sufficient history before retrying. The generated
GitHub Actions workflow uses `fetch-depth: 0`.

Without Git you can compare already available trees:

```bash
agent-config-score compare ../repo-base . --max-drop 0 --fail-on-new-errors
```

The baseline policy and suppressions govern both sides. A candidate cannot
increase its drop budget or suppress its newly introduced error to approve
itself. Trusted invocation-time overrides are explicit.

## 5. Read a failure and resolve it

- Exit `1` from `diff` / `compare` means the configured regression gate failed.
  Review new findings and the allowed score drop; fix the actual instructions
  rather than weakening the candidate policy.
- A suspected false positive needs review. An accepted exception can use a
  baseline-reviewed suppression with a stable rule ID, reason and expiry.
  It stays visible in the audit output. See [auditable exceptions](../README.md#auditable-exceptions).
- Exit `2` means the command could not perform the requested check, for example
  invalid configuration, a missing Git ref, or an unwritable report. This is
  **not** a clean result. Do not approve a change merely because no JSON appeared.

| Command | Exit 0 | Exit 1 | Exit 2 |
|---|---|---|---|
| Scan (`agent-config-score .`) | Scan completed; optional floor met | Score below configured floor | Invalid input or operational error |
| `diff`, `compare` | Baseline policy passed | New-error / score-drop gate failed | Comparison could not complete |
| `doctor` | No error checks; warnings may exist | One or more error checks | Argument / invocation error |
| Other commands | Requested operation completed | Not a lint gate | Invalid input or operational error |

Unexpected programming errors are not hidden by a catch-all handler. Report a
traceback after removing private content; passing the maintained tests does not
guarantee a bug-free program.

## 6. Save reports locally

```bash
agent-config-score . --json
agent-config-score . --html .agent-config-score/report.html --badge .agent-config-score/badge.svg --sarif .agent-config-score/results.sarif
agent-config-score diff --markdown .agent-config-score/regression.md
```

Keep generated reports outside supported instruction-file locations. JSON,
HTML, SARIF and regression reports can contain repository paths and finding
messages; inspect them before sharing. Do not overwrite your source or policy
files by choosing their paths as report destinations. Multiple output writes
are not a transaction: an earlier artifact may remain if a later write fails.

For a privacy-minimized draft instead:

```bash
agent-config-score feedback . --output .agent-config-score/case.md
```

Nothing is uploaded. Review and sanitize the draft yourself before sharing.

## Common setup problems

| Symptom | What to check |
|---|---|
| Command is not found | Install into the active Python environment; confirm its Scripts/bin directory is on PATH. In v0.23.0+, use `python -m agent_config_score` as a PATH-independent alternative. |
| Configuration / workflow encoding error | Save the file as UTF-8; do not copy a UTF-16 file into the integration. |
| Cannot write HTML, SARIF or Markdown | Choose a writable file path, not an existing directory; inspect parent-directory permissions. |
| `diff` cannot detect a baseline | Check `doctor`, then pass an available default-branch ref explicitly. |
| A prohibited command was flagged | Compare its exact context with the [supported prohibition grammar](instruction-context.md); arbitrary languages and paraphrases are not understood. |
| Historic GitHub run is red | Open the run for the current commit. Fixing a later commit does not erase an earlier failed run. |

Read the [limitations](limitations.md) before relying on the tool. Findings are
review signals, not a substitute for code review or a security assessment.
