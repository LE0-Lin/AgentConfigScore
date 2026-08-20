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

AgentConfigScore is a tiny, deterministic CLI that scores coding-agent configuration **and compares a PR against its base revision**. Instead of asking only “is this config good?”, it answers the question teams actually need in CI:

> **Did this change make our agent instructions worse?**

## The 10-second demo

```bash
# Scan one repository
agent-config-score .

# Compare a baseline with a candidate
agent-config-score compare /tmp/base . --max-drop 0 --fail-on-new-errors
```

```text
AgentConfigScore regression  A 96 → B 84 (-12)
New findings: 2   Resolved: 0

+ ERROR   curl-pipe-shell      Remote script piped directly to a shell
          .github/copilot-instructions.md:12
+ WARNING dead-path            Referenced path does not exist: src/legacy_auth.py
          AGENTS.md:31
```

That command exits non-zero, so the regression can block a pull request.

## Why another agent-config tool?

There are already good projects for linting the **current state** of agent instructions. AgentConfigScore deliberately focuses on a narrower job:

| | AgentConfigScore |
|---|---|
| Primary question | **Did this PR regress agent configuration?** |
| CI model | Baseline → candidate comparison |
| Output | Score delta + new/resolved findings |
| Runtime | Python standard library only |
| Network / API key | Not required |
| Scoring | Deterministic and explainable |
| Supported configs | AGENTS.md, CLAUDE.md, Cursor, Copilot, Gemini and more |

Think **regression gate**, not another AI reviewer.

## Quick start

```bash
git clone https://github.com/LE0-Lin/AgentConfigScore.git
cd AgentConfigScore
python -m pip install -e .
agent-config-score .
```

Generate a local HTML report and badge:

```bash
agent-config-score . \
  --html .agent-config-score/report.html \
  --badge .agent-config-score/badge.svg
```

Enforce an absolute score floor:

```bash
agent-config-score . --fail-under 90
```

## PR regression gate

For local use, compare any two checked-out trees:

```bash
agent-config-score compare ../repo-base . \
  --max-drop 0 \
  --fail-on-new-errors \
  --markdown regression.md
```

`--max-drop 0` means the score may not decrease at all. Set `--max-drop 3` if a small temporary drop is acceptable.

The repository includes `.github/workflows/config-regression.yml`, which automatically checks every pull request against `${{ github.event.pull_request.base.sha }}` and writes the result to the GitHub Actions Step Summary.

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

## Design principles

1. **Regression-first.** A legacy repo does not need to become perfect before CI becomes useful.
2. **Local-first.** No repository content is uploaded anywhere.
3. **Explainable.** Every score change maps to visible findings.
4. **Conservative.** Prefer a missed warning over noisy fake certainty.
5. **Zero runtime dependencies.** Python 3.10+ standard library only.

## Roadmap

- [x] deterministic 0–100 scoring
- [x] baseline → candidate regression comparison
- [x] Markdown PR/Step Summary report
- [x] GitHub Actions regression gate
- [ ] first-class reusable GitHub Action (`uses: LE0-Lin/AgentConfigScore@v1`)
- [ ] Git-aware `--base-ref origin/main` without manual worktrees
- [ ] SARIF output for GitHub code scanning
- [ ] score-history badge for public repositories
- [ ] optional semantic contradiction plugin

## Development

```bash
python -m pip install -e .
python -m unittest discover -s tests -v
agent-config-score . --fail-under 90
```

MIT licensed. Contributions and real-world agent-config failure examples are welcome.
