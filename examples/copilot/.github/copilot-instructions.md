# Repository instructions for GitHub Copilot

## Before editing

- Inspect the repository documentation, build configuration, and nearby tests.
- Reuse established patterns and dependencies unless the task requires a change.
- Keep the patch limited to the requested behavior and preserve unrelated work.

## Implementation and verification

- Make the smallest coherent change that solves the problem.
- Add or update a regression test when behavior changes or a bug is fixed.
- Run the repository's existing formatter, type checker, linter, and relevant tests.
- Never remove an assertion or lower a quality gate only to obtain a passing run.
- State which checks passed and clearly identify checks that could not be run.

## Safety

- Never print, commit, or reproduce secrets and credentials.
- Do not publish, deploy, delete data, or contact third parties without approval.
- Validate paths and targets before commands that overwrite or remove files.

## Final response

- Explain the outcome, the important files changed, verification performed, and known limitations.
