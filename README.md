# AgentConfigScore

<p align="center">
  <img src="assets/agent-config-score.svg" alt="AgentConfigScore A 100" />
</p>

<p align="center"><strong>Codecov for AI coding-agent instructions.</strong></p>

<p align="center">
  Stop pull requests from quietly making <code>AGENTS.md</code>, <code>CLAUDE.md</code>, Cursor, Copilot and Gemini instructions worse.
</p>

<p align="center">
  <a href="https://github.com/LE0-Lin/AgentConfigScore/actions/workflows/ci.yml"><img src="https://github.com/LE0-Lin/AgentConfigScore/actions/workflows/ci.yml/badge.svg" alt="CI" /></a>
  <img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python 3.10+" />
  <img src="https://img.shields.io/badge/runtime_dependencies-0-brightgreen" alt="0 runtime dependencies" />
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT" />
</p>

AgentConfigScore is a small, deterministic regression gate for coding-agent configuration. It compares a pull request with its base revision and answers one CI-friendly question:

> **Did this change make our agent instructions worse?**

## Get running in two commands

Install the rolling pre-1.0 release and initialize your repository:

```bash
python -m pip install "git+https://github.com/LE0-Lin/AgentConfigScore.git@v0"
agent-config-score init
```

`init` safely creates:

- `.agentconfigscore.json` — version-controlled regression policy
- `.github/workflows/agent-config-score.yml` — pull-request regression gate

Review and commit those two files. From then on, pull requests are checked automatically.

Initialization is deliberately conservative: it preflights every target before writing, never overwrites a conflicting file by default, and is idempotent when the generated files already match.

```bash
agent-config-score init --dry-run      # preview without writing
agent-config-score init --no-workflow  # policy file only
agent-config-score init --force        # intentionally replace conflicting generated files
```

### Manual GitHub Actions setup

If you prefer to create the workflow yourself, add `.github/workflows/agent-config-score.yml`:

```yaml
name: agent-config-regression

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
```

`v0` is the rolling stable ref for the current pre-1.0 series. Without a policy file, the Action keeps its conservative compatibility defaults: no score drop is allowed and newly introduced error findings fail the job.

The action installs AgentConfigScore, finds the PR base commit, compares it with the candidate, writes a Markdown report to the GitHub Actions Step Summary, and fails the job when the configured regression policy is violated.

## Keep policy in the repository

`agent-config-score init` starts with a conservative policy:

```json
{
  "version": 1,
  "policy": {
    "max_drop": 0,
    "fail_on_new_errors": true
  }
}
```

You can optionally add an absolute scan floor:

```json
{
  "version": 1,
  "policy": {
    "max_drop": 0,
    "fail_on_new_errors": true,
    "fail_under": 90
  }
}
```

| Policy key | Default | Meaning |
|---|---:|---|
| `max_drop` | `0` | Maximum score decrease allowed by `diff` / `compare` |
| `fail_on_new_errors` | `false` in CLI, `true` in the Action when no policy file exists | Fail regression checks on newly introduced error findings |
| `fail_under` | unset | Optional absolute score floor for a normal scan |

### Why baseline policy governs a PR

A pull request must not be able to disable the gate that reviews it.

For `diff` and `compare`, AgentConfigScore uses the **baseline** `.agentconfigscore.json` to decide pass/fail. The candidate policy is still parsed and validated, but its new thresholds only become active after the change is merged and becomes the baseline for a later PR.

That means a PR changing:

```json
{"policy":{"max_drop":100,"fail_on_new_errors":false}}
```

cannot use those weaker values to pass itself.

Explicit CLI or Action inputs remain available as trusted invocation-time overrides.

## Check locally before you push

Compare your current working tree with any local Git branch, tag, or commit:

```bash
agent-config-score diff origin/main
```

If the repository contains `.agentconfigscore.json`, the baseline policy is applied automatically. You can still override it explicitly when you intend to:

```bash
agent-config-score diff origin/main \
  --max-drop 3 \
  --no-fail-on-new-errors
```

`diff` includes **uncommitted changes** in the current working tree. AgentConfigScore creates an isolated detached worktree for the baseline ref, compares it with your repository, then removes the temporary worktree automatically.

It stays offline and never fetches a missing ref behind your back. If `origin/main` is not available locally, run `git fetch origin` yourself and retry.

You can run the command from any subdirectory inside the repository. Use `--path DIR` when you want to point at a different local repository.

## What a failing PR looks like

```text
AgentConfigScore regression  A 96 → B 84 (-12)
New findings: 2   Resolved: 0

+ ERROR   curl-pipe-shell      Remote script piped directly to a shell
          .github/copilot-instructions.md:12
+ WARNING dead-path            Referenced path does not exist: src/legacy_auth.py
          AGENTS.md:31
```

**Live proof:** [PR #6](https://github.com/LE0-Lin/AgentConfigScore/pull/6) deliberately added an unsafe `curl | bash` instruction. AgentConfigScore changed the score from **A 100 → B 82 (-18)**, reported one new `curl-pipe-shell` error, and failed the GitHub Actions job. The PR was then closed without merging.

This is intentionally different from an absolute quality gate. A legacy repository can start at 72/100 and still adopt AgentConfigScore immediately: a PR that stays at 72 passes, while a PR that drops to 65 fails.

## Why regression-first?

There are already good tools for linting the **current state** of AI-agent instructions. AgentConfigScore deliberately focuses on a narrower job:

| | AgentConfigScore |
|---|---|
| Primary question | **Did this PR regress agent configuration?** |
| CI model | Baseline → candidate comparison |
| Output | Score delta + new/resolved findings |
| Adoption | Existing imperfect repos can use it immediately |
| Runtime | Python standard library only |
| Network / API key | Not required |
| Scoring | Deterministic and explainable |
| Supported configs | AGENTS.md, CLAUDE.md, Cursor, Copilot, Gemini and more |

Think **regression gate**, not another AI reviewer.

## CLI reference

Initialize a repository:

```bash
agent-config-score init
```

Score the current repository without a baseline:

```bash
agent-config-score .
```

Inspect the complete rule catalog or one specific rule:

```bash
agent-config-score rules
agent-config-score rules curl-pipe-shell
agent-config-score rules --json
```

Run the Git-native regression check and save a Markdown report:

```bash
agent-config-score diff origin/main \
  --markdown regression.md
```

For scripts and custom integrations, add `--json` to either `diff` or `compare`.

Advanced: compare two already checked-out directory trees directly:

```bash
agent-config-score compare ../repo-base . \
  --markdown regression.md
```

Generate local HTML, badge, and SARIF reports:

```bash
agent-config-score . \
  --html .agent-config-score/report.html \
  --badge .agent-config-score/badge.svg \
  --sarif .agent-config-score/results.sarif
```

Enforce an absolute score floor directly when you want to override repository policy:

```bash
agent-config-score . --fail-under 90
```

Inspect the installed version and command overview:

```bash
agent-config-score --version
agent-config-score --help
```

## Understand every rule

AgentConfigScore has a stable rule catalog instead of hiding scoring logic inside the scanner. Every rule has one canonical definition containing:

- rule ID
- default severity
- scoring category
- penalty before category caps
- short summary
- longer explanation

For example:

```bash
agent-config-score rules curl-pipe-shell
```

prints the rule's severity, category, penalty, summary, and explanation. Use JSON when another tool needs the same contract:

```bash
agent-config-score rules --json
agent-config-score rules dead-path --json
```

The scanner, scoring categories, CLI rule inspection, and SARIF rule metadata all read from the same catalog. This keeps the human-facing explanation and machine-facing output aligned and provides a stable base for future rule suppression and policy controls.

## GitHub code scanning with SARIF

`--sarif` writes a SARIF 2.1.0 report with AgentConfigScore rule IDs, severity levels, source locations, descriptions, categories, and scoring penalties. That means findings can be uploaded into GitHub code scanning instead of living only in terminal output.

A minimal upload workflow for a public repository looks like this:

```yaml
name: agent-config-code-scanning

on:
  push:

permissions:
  contents: read
  security-events: write

jobs:
  scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: actions/setup-python@v7
        with:
          python-version: "3.12"
      - run: python -m pip install "git+https://github.com/LE0-Lin/AgentConfigScore.git@v0"
      - run: agent-config-score . --sarif agent-config-score.sarif
      - uses: github/codeql-action/upload-sarif@v4
        with:
          sarif_file: agent-config-score.sarif
          category: agent-config-score
```

The SARIF generator keeps repository-level findings such as cross-file duplication or missing canonical `AGENTS.md` as repository-level results instead of inventing fake file locations.

## What it checks today

| Check | What it catches |
|---|---|
| Context size | Oversized persistent instruction files |
| Cross-file duplication | Repeated meaningful rules across agent configs |
| Contradictions | Conservative exact-body `always` vs `never` conflicts |
| Dead paths | Referenced repository paths that no longer exist |
| Dangerous shell | `curl \| bash`, `wget \| sh`, `rm -rf`, `sudo`, `chmod 777` |
| Secret patterns | Common API token/private-key signatures |
| Canonical config | Multiple tool-specific files without a root `AGENTS.md` |
| **Regression diff** | New findings and score drops introduced by a change |

Supported discovery includes:

- `AGENTS.md`
- `CLAUDE.md`
- `GEMINI.md`
- `.cursorrules`
- `.cursor/rules/*.md` / `*.mdc`
- `.github/copilot-instructions.md`
- `.github/instructions/*.md`
- `.claude/**/*.md`
- `.clinerules` / `.windsurfrules`

## Action inputs

| Input | Default | Meaning |
|---|---:|---|
| `base-sha` | PR base SHA | Explicit baseline commit SHA |
| `max-drop` | empty | Optional trusted override for baseline `policy.max_drop` |
| `fail-on-new-errors` | empty | Optional trusted override for baseline `policy.fail_on_new_errors` |
| `python-version` | `3.12` | Python used by the composite action |

When the override inputs are empty, the Action uses the baseline repository policy. If no policy file exists, it preserves the historical Action defaults: `max_drop = 0` and `fail_on_new_errors = true`.

## Action outputs

The reusable action exposes structured numeric outputs so later workflow steps can build comments, dashboards, badges, or custom policy around the same deterministic comparison.

| Output | Meaning |
|---|---|
| `base-score` | Baseline AgentConfigScore |
| `head-score` | Candidate AgentConfigScore |
| `delta` | Candidate minus baseline score |
| `new-findings` | Number of newly introduced findings |
| `new-errors` | Number of newly introduced error-severity findings |
| `resolved-findings` | Number of findings resolved by the candidate |

```yaml
- name: Check agent config
  id: acs
  uses: LE0-Lin/AgentConfigScore@v0

- name: Print regression metrics
  if: always()
  run: |
    echo "score: ${{ steps.acs.outputs.base-score }} -> ${{ steps.acs.outputs.head-score }}"
    echo "delta: ${{ steps.acs.outputs.delta }}"
    echo "new errors: ${{ steps.acs.outputs.new-errors }}"
```

The action emits these values before returning the final regression exit status. Use `if: always()` on a later step when you want to consume the metrics even after AgentConfigScore intentionally fails the job.

## Design principles

1. **Regression-first.** A legacy repo does not need to become perfect before CI becomes useful.
2. **Baseline-governed policy.** A candidate change cannot weaken the gate evaluating itself.
3. **Local-first.** Repository content is not uploaded to a hosted analysis service.
4. **Explainable.** Every score change maps to visible findings and stable rule metadata.
5. **Conservative.** Prefer a missed warning over noisy fake certainty.
6. **Zero runtime dependencies.** Python 3.10+ standard library only.

## Roadmap

- [x] deterministic 0–100 scoring
- [x] baseline → candidate regression comparison
- [x] Markdown PR / Step Summary report
- [x] first-class reusable GitHub Action
- [x] structured GitHub Action outputs
- [x] self-dogfooding PR regression workflow
- [x] SARIF output for GitHub code scanning
- [x] Git-aware local diff without manual worktrees
- [x] baseline-governed repository policy/config file
- [x] safe one-command repository initialization
- [x] stable rule catalog and rule-inspection command
- [ ] reasoned / expiring rule suppression
- [ ] score-history badge for public repositories
- [ ] optional semantic contradiction plugin

## Development

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
agent-config-score . --fail-under 90
```

MIT licensed. Contributions and real-world agent-config failure examples are welcome.

If AgentConfigScore catches a regression in your repository, a ⭐ helps other maintainers discover it.
