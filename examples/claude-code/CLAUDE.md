# Repository instructions for Claude Code

## Workflow

- Understand the requested outcome and inspect relevant code before editing.
- Match existing repository conventions and avoid unrelated refactors.
- Prefer repository-provided build and test commands.

## Quality gates

- Add a focused regression test for changed behavior whenever practical.
- Run the narrowest relevant test first, followed by the standard project checks.
- Never conceal a failure or weaken a check merely to finish the task.
- Report both successful checks and anything that remains unverified.

## Safety

- Never expose credentials, tokens, private keys, or personal data.
- Ask before destructive actions, publishing, deployment, or external communication.
- Preserve user changes that are outside the requested scope.

## Handoff

- Summarize the result, important files changed, tests run, and remaining risks.
