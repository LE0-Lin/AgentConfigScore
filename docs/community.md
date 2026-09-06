# Community and Contribution

## Getting started

AgentConfigScore welcomes improvements from users of AI coding tools.

Good first contributions:

- Add examples for new coding agents.
- Improve documentation.
- Add regression rules with tests.
- Share a sanitized real-world hit, false positive, or false negative using the **Real-world case** issue form.
- Improve reports and developer experience.

Generate a privacy-minimized case draft locally:

```bash
agent-config-score feedback . --output agent-config-score-case.md
```

The command uploads nothing and excludes repository names, file paths,
instruction text, finding messages, and suppression reasons. Review the file,
complete its observation prompts, then copy the relevant sections into the
**Real-world case** issue form.

## Feature requests

Open an issue describing:

1. The workflow you want to protect.
2. The AI coding agent involved.
3. Why existing checks are insufficient.

## Before contributing

Please run:

```bash
python -m unittest discover -s tests -v
agent-config-score doctor
```

Keep changes focused and include tests for behavior changes.
