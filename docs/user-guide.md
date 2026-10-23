# User guide

English | [简体中文](simplified/user-guide.md) | [繁體中文](traditional/user-guide.md)

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

In v0.24.0+, removal checks only exempt one-to-one exact-text
moves to newly added files in the same directory. Existing copies and moving root
rules into a subtree do not hide removal. Comparisons reuse scan-time text instead
of reopening sources; keep both trees stable and rerun after edits. See
[regression coverage and limits](regression-coverage.md). A regression-only error
may occur with two `100` scores: the example above enables new-error blocking;
the bare CLI without a policy remains score-only by default.

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

v0.24.0+ also retains the declared tool version and a best-effort
tool-source SHA-256 in JSON, HTML, SARIF and new history snapshots. Compare/diff
JSON retains both scan identities. This distinguishes local implementations with
the same version, not accuracy or reproducibility by itself. Missing source makes
the digest unavailable, not the scan invalid. See [report identity](report-identity.md)
for coverage, compatibility and environment/input limits; older reports are not relabelled.

For a privacy-minimized draft instead:

```bash
agent-config-score feedback . --output .agent-config-score/case.md
```

Nothing is uploaded. Review and sanitize the draft yourself before sharing.

## Optional: review missing deletion safeguards (v0.24.0+)

```bash
agent-config-score guardrails . --file AGENTS.md
agent-config-score guardrails . --file AGENTS.md --template-language simplified --json
```

This independent command gives unscored, selected-file advice. No recognized
constraint means “review needed,” not “unsafe.” Default previews change nothing.
After reviewing the full policy context and addition, rerun the same command
with `--apply TOKEN` using its exact printed confirmation. Changed input requires
a new preview; ambiguous markup and aliases require manual merging. English,
Simplified and Traditional addition templates do not localize CLI messages.
Explicitly labeled example sections do not count as active policy; if such a
section remains open at end of file, automatic append is unavailable. A few
explicit approval-bypass directives produce line-only `review_signals` and
disable append even when another constraint is recognized. Resolve those
policies manually; this is not a general contradiction detector.
See [guardrail suggestions](guardrail-suggestions.md) for grammar, scope, privacy
and non-atomic/partial-write limits. Existing scoring and CI defaults are unchanged.

## Optional: actionable maintainer results (v0.24.0+)

```bash
agent-config-score . --explain
agent-config-score diff --explain --markdown .agent-config-score/regression.md
agent-config-score init --pr-comment --dry-run
```

`--explain` adds static next steps to active scan/new regression findings in
text/Markdown, not JSON, scores or exit policy. It does not execute commands or
repair files. The [best-practice checklist](best-practices.md) is also unscored.
`init --pr-comment` opts into a generated same-repository PR comment workflow and
discloses `pull-requests: write`; the default generated workflow keeps read-only
GitHub permissions. Preview,
review and commit only one workflow. Existing conflicts require deliberate
review, not an automatic overwrite. Fork PRs use job summaries without comments.
The generated Action ref remains rolling `v0`; explanations require v0.24.0+
or a verified Action revision containing this feature. Older pinned workflows
remain unchanged when you upgrade the local CLI.
See the [maintainer workflow](maintainer-workflow.md) for setup and limits.

To update only CI without reading/resetting custom policy (v0.24.0+):

```bash
agent-config-score init --workflow-only --pr-comment --force --dry-run
agent-config-score init --workflow-only --pr-comment --force
```

Compare the recipe with existing workflow customizations before the second
command: `--force` replaces that workflow, not a YAML merge. The policy file is
out of scope even if missing or invalid; run `doctor` separately. Selected linked,
reparse or shared files need manual setup. Initialization prints the generated
Action ref, which may differ from the installed CLI; it does not update remote
refs. Writes are preflighted, not an atomic filesystem transaction.

## Common setup problems

| Symptom | What to check |
|---|---|
| Command is not found | Install into the active Python environment; confirm its Scripts/bin directory is on PATH. In v0.23.0+, use `python -m agent_config_score` as a PATH-independent alternative. |
| Configuration / workflow encoding error | Save the file as UTF-8; do not copy a UTF-16 file into the integration. |
| Cannot write HTML, SARIF or Markdown | Choose a writable file path, not an existing directory; inspect parent-directory permissions. |
| `Unable to read repository path index` | Run `doctor` and check its `repository-paths` error. Fix directory access or I/O failures; no success report is emitted from a partial index. |
| Scanner source resolution/read error | Inspect selected instruction and ignore-file links locally. They must point to in-repository regular files; fix dangling links, cycles or permissions. `doctor` reports an `instructions` error. Do not treat an incomplete scan as a passing score. |
| `diff` cannot detect a baseline | Check `doctor`, then pass an available default-branch ref explicitly. |
| A prohibited command was flagged | Compare its exact context with the [supported prohibition grammar](instruction-context.md); arbitrary languages and paraphrases are not understood. |
| Historic GitHub run is red | Open the run for the current commit. Fixing a later commit does not erase an earlier failed run. |

Read the [limitations](limitations.md) before relying on the tool. Findings are
review signals, not a substitute for code review or a security assessment.
