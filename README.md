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
  <img src="https://img.shields.io/badge/platforms-Linux%20%7C%20Windows%20%7C%20macOS-informational" alt="Linux, Windows, macOS" />
  <img src="https://img.shields.io/badge/runtime_dependencies-0-brightgreen" alt="0 runtime dependencies" />
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT" />
</p>

AgentConfigScore is a deterministic regression gate for coding-agent configuration. It compares a change with its baseline and answers one CI-friendly question:

> **Did this change make our agent instructions worse?**

It is regression-first rather than perfection-first: an existing repository can start at 72/100 and adopt the gate immediately. A pull request that stays at 72 can pass; one that drops to 65 can fail.

## Get running

```bash
python -m pip install "git+https://github.com/LE0-Lin/AgentConfigScore.git@v0"
agent-config-score init
```

`init` safely creates:

- `.agentconfigscore.json` — version-controlled policy, suppressions, and editor schema annotation
- `.github/workflows/agent-config-score.yml` — pull-request regression gate

Review and commit those files. Pull requests are then checked automatically.

Validate the integration and run the same regression check locally before pushing:

```bash
agent-config-score doctor
agent-config-score diff
```

`diff` auto-detects a safe local default-branch baseline when possible. You can still pass an explicit ref such as `origin/main` whenever you want full control.

Initialization is conservative: every target is preflighted before anything is written, conflicting files are never overwritten by default, and rerunning against matching generated files is idempotent.

```bash
agent-config-score init --dry-run      # preview without writing
agent-config-score init --no-workflow  # config only
agent-config-score init --force        # intentionally replace conflicting generated files
```

`v0` is the rolling stable ref for the current pre-1.0 series.

## Repository policy + editor validation

A generated config looks like this:

```json
{
  "$schema": "https://raw.githubusercontent.com/LE0-Lin/AgentConfigScore/v0/schema/agentconfigscore.schema.json",
  "version": 1,
  "policy": {
    "max_drop": 0,
    "fail_on_new_errors": true
  }
}
```

The `$schema` annotation enables live validation and completion in editors that support JSON Schema. It can catch misspelled policy keys, wrong value types, unknown suppression rule IDs, missing suppression fields, and malformed path scopes before CI runs.

The schema is Draft 2020-12 and lives at `schema/agentconfigscore.schema.json`. AgentConfigScore's tests verify that its suppression rule enum stays exactly aligned with the stable Rule Catalog, so editor hints cannot silently drift away from scanner behavior.

Policy fields:

| Key | Default | Meaning |
|---|---:|---|
| `max_drop` | `0` | Maximum score decrease allowed by `diff` / `compare` |
| `fail_on_new_errors` | `false` in the CLI; `true` in the Action when no policy file exists | Fail on newly introduced active error findings |
| `fail_under` | unset | Optional absolute score floor for a normal scan |

An absolute floor is optional:

```json
{
  "$schema": "https://raw.githubusercontent.com/LE0-Lin/AgentConfigScore/v0/schema/agentconfigscore.schema.json",
  "version": 1,
  "policy": {
    "max_drop": 0,
    "fail_on_new_errors": true,
    "fail_under": 90
  }
}
```

### Why the baseline policy governs a PR

A pull request must not be able to weaken the gate that reviews it.

For `diff`, `compare`, and the reusable GitHub Action, AgentConfigScore uses the **baseline** policy to decide pass/fail. The candidate config is still parsed and validated, but new thresholds only become active after that config is reviewed, merged, and becomes a later baseline.

A candidate changing `max_drop` to `100` therefore cannot use that weaker value to pass itself. Explicit CLI or Action inputs remain available as trusted invocation-time overrides.

## Auditable exceptions

Sometimes a finding is understood and intentionally accepted. AgentConfigScore supports suppressions, but does not treat them as a permanent ignore list.

Every suppression must name a stable rule, explain the exception, and expire:

```json
{
  "$schema": "https://raw.githubusercontent.com/LE0-Lin/AgentConfigScore/v0/schema/agentconfigscore.schema.json",
  "version": 1,
  "policy": {
    "max_drop": 0,
    "fail_on_new_errors": true
  },
  "suppressions": [
    {
      "rule": "dead-path",
      "reason": "Generated docs reference paths that only exist after deployment.",
      "expires": "2026-12-31",
      "paths": ["docs/**"]
    }
  ]
}
```

Rules for suppressions:

- `rule` must be a known stable AgentConfigScore rule ID
- `reason` must be non-empty and is limited to 500 characters
- `expires` must be `YYYY-MM-DD`
- an expired suppression is a configuration error; remove it or explicitly renew it
- `paths` is optional and accepts unique instruction-file glob patterns
- path-scoped suppressions never hide repository-level findings such as cross-file contradiction
- duplicate rule/path scopes are rejected

Suppressions are **not silent**. A matching finding stops contributing to score and regression decisions, but remains visible in the `suppressed_findings` audit trail in JSON and is shown with its reason and expiry in terminal, HTML, and Markdown output.

Suppressions are baseline-governed too: a PR cannot add a suppression and use it to excuse a finding introduced by that same PR. The baseline suppression set is applied to both sides of a regression comparison.

## Check locally before you push

The common path is now zero-config:

```bash
agent-config-score doctor
agent-config-score diff
```

`doctor` validates the repository integration. `diff` compares the current working tree—including uncommitted changes—with a safe local default-branch baseline.

When no `BASE_REF` is provided, AgentConfigScore detects a baseline conservatively in this order:

1. locally configured `origin/HEAD`
2. local `main`
3. local `master`
4. local `trunk`
5. an upstream whose branch name itself is `main`, `master`, or `trunk`

It deliberately does **not** use a feature-branch upstream such as `origin/my-feature` as the baseline, because doing so could hide committed changes relative to the real default branch.

AgentConfigScore creates an isolated detached baseline worktree, compares it with your current repository, then removes the temporary worktree automatically. Automatic detection is fully offline and never runs `git fetch`.

If no safe local baseline can be identified, pass one explicitly:

```bash
agent-config-score diff origin/main
```

If that ref is not available locally, fetch it yourself and retry. AgentConfigScore never fetches a missing ref behind your back.

Trusted threshold overrides are explicit:

```bash
agent-config-score diff \
  --max-drop 3 \
  --no-fail-on-new-errors
```

You can run `diff` from any subdirectory inside the repository. Use `--path DIR` to point at another local repository.

## What a failing PR looks like

```text
AgentConfigScore regression  A 96 → B 84 (-12)
New findings: 2   Resolved: 0   Suppressed: 0

+ ERROR   curl-pipe-shell      Remote script piped directly to a shell
          .github/copilot-instructions.md:12
+ WARNING dead-path            Referenced path does not exist: src/legacy_auth.py
          AGENTS.md:31
```

**Live proof:** [PR #6](https://github.com/LE0-Lin/AgentConfigScore/pull/6) deliberately added an unsafe `curl | bash` instruction. AgentConfigScore changed the score from **A 100 → B 82 (-18)**, reported a new `curl-pipe-shell` error, failed the GitHub Actions job, and the PR was closed without merging.

## Manual GitHub Actions setup

If you do not want to use `init`, create `.github/workflows/agent-config-score.yml` yourself:

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

The Action installs AgentConfigScore, resolves the PR base commit, applies baseline policy and suppressions, writes a Markdown report to the GitHub Actions Step Summary, exposes structured outputs, and returns the final regression status.

Without a policy file, the Action preserves its conservative compatibility defaults: `max_drop = 0` and `fail_on_new_errors = true`.

## Stable rule catalog

Scoring logic is not hidden inside prose. Every rule has one canonical definition containing:

- rule ID
- default severity
- scoring category
- penalty before category caps
- short summary
- longer explanation

Inspect all rules or one rule:

```bash
agent-config-score rules
agent-config-score rules curl-pipe-shell
agent-config-score rules --json
agent-config-score rules dead-path --json
```

The scanner, scoring categories, CLI rule inspection, SARIF metadata, suppression validation, and config JSON Schema all derive from or are tested against the same stable catalog.

Current rule families include context size, cross-file duplication, contradictions, dead paths, dangerous shell commands, common credential patterns, and missing canonical `AGENTS.md` coordination.

## CLI reference

Score the current repository:

```bash
agent-config-score .
```

Validate the repository integration:

```bash
agent-config-score doctor
agent-config-score doctor --json
```

Run a local regression check with automatic baseline detection:

```bash
agent-config-score diff
```

Save a regression Markdown report:

```bash
agent-config-score diff --markdown regression.md
```

Use an explicit baseline when needed:

```bash
agent-config-score diff origin/main
```

Advanced: compare two already checked-out trees directly:

```bash
agent-config-score compare ../repo-base . --markdown regression.md
```

Generate local reports:

```bash
agent-config-score . \
  --html .agent-config-score/report.html \
  --badge .agent-config-score/badge.svg \
  --sarif .agent-config-score/results.sarif
```

Override an absolute floor:

```bash
agent-config-score . --fail-under 90
```

Machine-readable output is available with `--json` for scans, `doctor`, `diff`, `compare`, and the rule catalog.

```bash
agent-config-score --version
agent-config-score --help
```

## GitHub code scanning with SARIF

`--sarif` writes SARIF 2.1.0 with rule IDs, severity, source location, descriptions, categories, and scoring penalties. Active findings can therefore be uploaded into GitHub code scanning. Suppressed findings remain in AgentConfigScore's explicit audit output rather than being emitted as active SARIF results.

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

Repository-level findings remain repository-level SARIF results instead of receiving invented file locations.

## What it scans

Supported discovery includes:

- `AGENTS.md`
- `CLAUDE.md`
- `GEMINI.md`
- `.cursorrules`
- `.cursor/rules/*.md` / `*.mdc`
- `.github/copilot-instructions.md`
- `.github/instructions/*.md`
- `.claude/**/*.md`
- `.clinerules`
- `.windsurfrules`

`.agentconfigscoreignore` can exclude discovery paths when needed.

## Action inputs

| Input | Default | Meaning |
|---|---:|---|
| `base-sha` | PR base SHA | Explicit baseline commit SHA |
| `max-drop` | empty | Optional trusted override for baseline `policy.max_drop` |
| `fail-on-new-errors` | empty | Optional trusted override for baseline `policy.fail_on_new_errors` |
| `python-version` | `3.12` | Python used by the composite action |

## Action outputs

| Output | Meaning |
|---|---|
| `base-score` | Baseline AgentConfigScore |
| `head-score` | Candidate AgentConfigScore |
| `delta` | Candidate minus baseline score |
| `new-findings` | Number of newly introduced active findings |
| `new-errors` | Number of newly introduced active error findings |
| `resolved-findings` | Number of active findings resolved by the candidate |

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

The Action emits outputs before returning its final regression status. Use `if: always()` when a downstream step must consume metrics even after the gate intentionally fails.

## Design principles

1. **Regression-first.** Existing repositories do not have to become perfect before CI becomes useful.
2. **Baseline-governed policy.** A candidate cannot weaken the gate evaluating itself.
3. **Auditable exceptions.** Suppressions need a reason and expiry, remain visible, and cannot self-authorize.
4. **Local-first.** Repository content is not uploaded to a hosted analysis service, and automatic Git baseline detection does not fetch.
5. **Explainable.** Scores map to stable rule IDs and visible findings.
6. **Conservative.** Prefer a missed warning over noisy fake certainty.
7. **Zero runtime dependencies.** Python 3.10+ standard library only.

## Roadmap

- [x] deterministic 0–100 scoring
- [x] baseline → candidate regression comparison
- [x] Markdown PR / Step Summary report
- [x] first-class reusable GitHub Action
- [x] structured GitHub Action outputs
- [x] SARIF output for GitHub code scanning
- [x] Git-aware local diff without manual worktrees
- [x] automatic local default-branch baseline detection
- [x] baseline-governed repository policy
- [x] safe one-command repository initialization
- [x] repository integration doctor
- [x] stable Rule Catalog and rule inspection
- [x] reasoned / expiring suppressions
- [x] JSON Schema + editor validation
- [x] end-to-end behavior contract fixtures
- [ ] score-history artifact / badge workflow
- [ ] optional semantic contradiction plugin

## Development

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
agent-config-score . --fail-under 90
```

MIT licensed. Contributions and real-world agent-config failure examples are welcome.

If AgentConfigScore catches a regression in your repository, a ⭐ helps other maintainers discover it.
