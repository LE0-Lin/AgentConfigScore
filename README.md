# AgentConfigScore

<p align="center">
  <img src="https://raw.githubusercontent.com/LE0-Lin/AgentConfigScore/main/assets/agent-config-score.svg" alt="AgentConfigScore A 100" />
</p>

<p align="center"><strong>Codecov for AI coding-agent instructions.</strong></p>

<p align="center">
  Stop pull requests from quietly making <code>AGENTS.md</code>, <code>CLAUDE.md</code>, Cursor, Copilot and Gemini instructions worse.
</p>

<p align="center">
  <a href="https://github.com/LE0-Lin/AgentConfigScore/actions/workflows/ci.yml"><img src="https://github.com/LE0-Lin/AgentConfigScore/actions/workflows/ci.yml/badge.svg" alt="CI" /></a>
  <a href="https://pypi.org/project/agent-config-score/"><img src="https://img.shields.io/pypi/v/agent-config-score" alt="PyPI" /></a>
  <img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python 3.10+" />
  <img src="https://img.shields.io/badge/platforms-Linux%20%7C%20Windows%20%7C%20macOS-informational" alt="Linux, Windows, macOS" />
  <img src="https://img.shields.io/badge/runtime_dependencies-0-brightgreen" alt="0 runtime dependencies" />
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT" />
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/LE0-Lin/AgentConfigScore/main/assets/agent-config-score-demo.gif" alt="AgentConfigScore detects an instruction regression and blocks the pull request" width="100%" />
</p>

AgentConfigScore is a deterministic regression gate for coding-agent configuration. It compares a change with its baseline and answers one CI-friendly question:

> **Did this change make our agent instructions worse?**

It is regression-first rather than perfection-first: an existing repository can start at 72/100 and adopt the gate immediately. A pull request that stays at 72 can pass; one that drops to 65 can fail.

> [!IMPORTANT]
> **A 100 means no active deterministic rule matched—not that the instructions are semantically perfect.** AgentConfigScore is a focused linter, not an AI judge. See the public [score contract and known blind spots](https://github.com/LE0-Lin/AgentConfigScore/blob/main/docs/limitations.md).

| What usually goes wrong | What the gate does |
|---|---|
| A pull request weakens its own quality threshold | Uses the baseline branch's policy to judge the change |
| A new instruction contradicts or duplicates existing guidance | Reports deterministic, line-addressable findings |
| A pull request deletes an instruction file or reverses an exact directive | Emits a regression-only error even when ordinary score arithmetic would miss it |
| An exception becomes a permanent silent ignore | Requires a reason and expiry, then preserves an audit trail |
| A scanner update becomes noisy on real projects | Replays a pinned, manually reviewed [real-repository benchmark](https://github.com/LE0-Lin/AgentConfigScore/blob/v0/benchmarks/README.md) |

<p align="center">
  <img src="https://raw.githubusercontent.com/LE0-Lin/AgentConfigScore/main/assets/agent-config-score-workflow.svg" alt="Configure once, guard every pull request, and keep evidence" width="100%" />
</p>

See the complete [visual tour](https://github.com/LE0-Lin/AgentConfigScore/blob/main/docs/visual-tour.md) for setup, regression, and history demos.

## Get running

```bash
python -m pip install agent-config-score
agent-config-score init
```

<p align="center">
  <img src="https://raw.githubusercontent.com/LE0-Lin/AgentConfigScore/main/assets/agent-config-score-setup.gif" alt="Install AgentConfigScore, initialize a repository, and verify the integration" width="100%" />
</p>

To test the latest stable pre-1.0 source directly from GitHub instead:

```bash
python -m pip install "git+https://github.com/LE0-Lin/AgentConfigScore.git@v0"
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

### Want the score directly on the pull request?

The Action stays read-only by default and writes the detailed regression report to the GitHub Actions job summary. If your repository prefers a visible PR conversation comment, use the [copy-ready opt-in PR comment recipe](docs/pr-comments.md). It keeps write permission in the caller workflow instead of silently expanding AgentConfigScore's privileges.

## Copy-ready templates

Start with a conservative template, then replace generic guidance with your
repository's real commands, architecture, and ownership boundaries:

- [Cursor Project Rule](https://github.com/LE0-Lin/AgentConfigScore/blob/main/examples/cursor/.cursor/rules/project.mdc)
- [GitHub Copilot instructions](https://github.com/LE0-Lin/AgentConfigScore/blob/main/examples/copilot/.github/copilot-instructions.md)
- [Gemini CLI context](https://github.com/LE0-Lin/AgentConfigScore/blob/main/examples/gemini/GEMINI.md)
- [Claude Code instructions](https://github.com/LE0-Lin/AgentConfigScore/blob/main/examples/claude-code/CLAUDE.md)

The [examples guide](https://github.com/LE0-Lin/AgentConfigScore/tree/main/examples) includes exact target paths and copy commands.

<!-- The remainder of the README is intentionally preserved in the repository history; this update should not truncate it. -->