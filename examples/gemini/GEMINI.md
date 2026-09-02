# Repository instructions for Gemini CLI

## Understand the repository

- Read the project documentation and inspect relevant implementation and tests before changing code.
- Follow established architecture, style, and dependency choices.
- Keep edits scoped to the requested outcome and preserve unrelated user work.

## Build and verify

- Use the repository's existing scripts and package manager.
- Add a regression test when fixing a bug or changing observable behavior.
- Run focused tests first, then the normal formatter, linter, type checker, and test suite.
- Never suppress a failure or weaken a quality threshold merely to make checks pass.
- Report exact verification results and clearly call out anything not run.

## Operate safely

- Never reveal secrets, credentials, private data, or environment values.
- Ask before destructive changes, releases, deployments, or messages to third parties.
- Check command targets before overwriting, moving, or deleting files.

## Complete the task

- Explain the result, important files changed, verification performed, and remaining limitations.
