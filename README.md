# AgentConfigScore

![Agent config score](assets/agent-config-score.svg)

**Lighthouse for AI coding-agent configs.**

[![CI](https://github.com/LE0-Lin/AgentConfigScore/actions/workflows/ci.yml/badge.svg)](https://github.com/LE0-Lin/AgentConfigScore/actions/workflows/ci.yml) ![Python](https://img.shields.io/badge/python-3.10%2B-blue) ![License](https://img.shields.io/badge/license-MIT-green)

Score and audit `AGENTS.md`, `CLAUDE.md`, Cursor rules, GitHub Copilot instructions, Gemini instructions, and common agent config files — locally, deterministically, and without sending your repository anywhere.

> Status: **v0.1 MVP** — small rule set, deliberately conservative. The goal is explainable findings rather than an opaque AI score.

## Why this exists

Coding-agent instructions are becoming part of the codebase. They also quietly accumulate problems:

- duplicated rules across `AGENTS.md`, `CLAUDE.md`, Cursor and Copilot;
- stale file paths after refactors;
- contradictory "always" / "never" instructions;
- huge persistent context files that burn tokens every session;
- dangerous shell snippets or accidentally committed credentials.

AgentConfigScore turns those problems into one simple number and an actionable report.

## Quick start

```bash
git clone https://github.com/LE0-Lin/AgentConfigScore.git
cd AgentConfigScore
python -m pip install -e .
agent-config-score .
```

Or scan another repository directly after installation:

```bash
agent-config-score /path/to/repository
```

Example:

```text
AgentConfigScore  B  84/100
Files: 4   Estimated tokens: 1,248   Duplication: 22%

! WARNING duplication          22% of meaningful instruction lines are duplicated across files
✖ ERROR   contradiction        Conflicting directives about: 'modify generated files'
! WARNING dead-path            Referenced path does not exist: src/legacy_auth.py
```

Generate a shareable offline report and badge:

```bash
agent-config-score . \
  --html .agent-config-score/report.html \
  --badge .agent-config-score/badge.svg
```

Use it in CI:

```bash
agent-config-score . --fail-under 80
```

Ignore intentional fixtures or generated examples with `.agentconfigscoreignore`:

```gitignore
examples/demo/**
vendor/**
```

## What v0.1 checks

| Check | What it catches |
|---|---|
| Context size | Oversized persistent instruction files |
| Cross-file duplication | Repeated meaningful rules across agent configs |
| Contradictions | Conservative exact-body `always` vs `never` conflicts |
| Dead paths | Referenced repo paths that no longer exist |
| Dangerous shell | `curl | bash`, `wget | sh`, `rm -rf`, `sudo`, `chmod 777` |
| Secret patterns | Common API token/private-key signatures |
| Canonical config | Multiple tool-specific files without a root `AGENTS.md` |

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

## Design principles

1. **Local-first.** No network request is required to scan a repository.
2. **Explainable.** Every point deduction maps to a visible finding.
3. **Conservative.** Prefer a missed warning over noisy fake certainty.
4. **Fast.** v0.1 uses Python's standard library only at runtime.
5. **CI-friendly.** JSON output and `--fail-under` make the score enforceable.

## Roadmap

- [ ] smarter semantic contradiction detection with an optional local-model mode;
- [ ] GitHub Action that comments the score on pull requests;
- [ ] historical score trend (`git`-aware regression detection);
- [ ] token-cost breakdown per coding agent;
- [ ] auto-fix for duplicated canonical instructions;
- [ ] hosted badge endpoint for public repositories;
- [ ] SARIF output for GitHub code scanning.

## Development

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
agent-config-score examples/demo --html /tmp/agent-config-score.html
```
