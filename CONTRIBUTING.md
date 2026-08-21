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

## Pull requests

Keep PRs focused. Describe the behavior change, add tests when behavior changes, and run the full unit suite before submitting.

Please avoid adding network calls or runtime dependencies to the core scanner unless there is a strong reason. Optional integrations should stay clearly separated from deterministic local analysis.

## Security-sensitive fixtures

Never commit real credentials, private keys, tokens, or private repository content as test data. Use unmistakably synthetic placeholders that cannot authenticate anywhere.
