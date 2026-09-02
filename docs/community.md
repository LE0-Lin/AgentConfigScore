# Community and Contribution

## Getting started

AgentConfigScore welcomes improvements from users of AI coding tools.

Good first contributions:

- Add examples for new coding agents.
- Improve documentation.
- Add regression rules with tests.
- Share a sanitized real-world hit, false positive, or false negative using the **Real-world case** issue form.
- Improve reports and developer experience.

## Feature requests

Open an issue describing:

1. The workflow you want to protect.
2. The AI coding agent involved.
3. Why existing checks are insufficient.

## Before contributing

Please run:

```bash
python -m pytest
agent-config-score doctor
```

Keep changes focused and include tests for behavior changes.
