# Contributing to AgentConfigScore

Thanks for helping improve AgentConfigScore. The project intentionally stays small, deterministic, explainable, and dependency-free at runtime.

## Development setup

```bash
git clone https://github.com/LE0-Lin/AgentConfigScore.git
cd AgentConfigScore
python -m pip install -e .
python -m unittest discover -s tests -v
agent-config-score . --fail-under 90
```

Python 3.10+ is supported.

## What makes a good contribution

- A regression test for every scanner false positive or false negative you fix.
- Conservative detection rules that can explain exactly why a finding exists.
- Improvements to PR-regression behavior, GitHub Actions integration, or reporting.
- Real-world examples of agent-instruction failures that can be reduced to safe test fixtures.
- Documentation that makes adoption simpler.

## Contribute a real-world regression fixture

Issue [#8](https://github.com/LE0-Lin/AgentConfigScore/issues/8) collects real failures from `AGENTS.md`, `CLAUDE.md`, Cursor, Copilot, Gemini, and similar instruction files. Sanitized examples are especially useful because they can turn into deterministic regression tests.

A useful fixture contribution is intentionally small:

1. Remove company names, credentials, private paths, and unrelated instructions.
2. Keep only the minimum text needed to reproduce the failure mode.
3. Add or update a test in `tests/` that fails before the fix and passes after it.
4. Run `python -m unittest discover -s tests -v` and `agent-config-score . --fail-under 90`.
5. In the pull request, explain the real-world failure in one or two sentences and why the proposed check is conservative.

You do **not** need to share a private repository. A synthetic fixture that faithfully reproduces the failure is preferred.

Good examples include stale referenced paths after a refactor, conflicting instructions across tools, unsafe shell guidance, accidental secret-like content, or instruction growth/duplication that creates a clear deterministic regression.

## Pull requests

Keep PRs focused. Describe the behavior change, add tests when behavior changes, and run the full unit suite before submitting.

Please avoid adding network calls or runtime dependencies to the core scanner unless there is a strong reason. Optional integrations should stay clearly separated from deterministic local analysis.

## Security-sensitive fixtures

Never commit real credentials, private keys, tokens, or private repository content as test data. Use unmistakably synthetic placeholders that cannot authenticate anywhere.
