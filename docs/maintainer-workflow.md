# Maintainer workflow: findings, next steps and one PR comment

`--explain` and `init --pr-comment` are **unreleased source features** after
v0.23.0. The current PyPI package, release tags and rolling `v0` Action have not
been updated. Commands below require a source build containing these changes.
The existing [copy-ready comment recipe](../examples/pr-comment.yml) also works
with the published Action, but that version's job summary has no new next-step
guidance. Generating a workflow does not change which Action revision it uses.

## 1. Inspect concrete problems locally

```bash
agent-config-score . --explain
agent-config-score rules dead-path
agent-config-score rules prompt-injection-override
```

Each active finding retains its rule ID, severity, message and location, followed
by a static next step. For example, a missing path asks you to verify its intended
scope and update/remove the stale reference, not create a placeholder just to
make the warning disappear. A credential finding recommends revocation/rotation
if real, rather than repeating its value. General guidance is also available in
the [unscored best-practice checklist](best-practices.md).

The command changes no instruction files, executes no referenced commands and
uploads nothing. Suggestions are **review guidance, not automatic fixes**.
`--explain` changes only text/Markdown presentation, not scores, findings,
suppressions, JSON, SARIF, HTML or exit policy. Suppressed/resolved findings do
not get new fix prompts. A clean scan gets no generic missing-keyword advice.

## 2. Review only changes against the baseline

```bash
agent-config-score diff --explain --markdown .agent-config-score/regression.md
```

Use an explicit baseline ref if automatic local detection is not appropriate.
The baseline policy and suppressions still govern the comparison. Guidance is
attached only to new findings, so unchanged historical findings do not become
new fix requests on every PR. Review accepted exceptions separately.

The Action in this source revision requests explanatory Markdown in its job
summary automatically. It does not publish a comment unless a caller workflow
opts in. Generated comments contain validated numeric results and a link to
details, not raw instruction text or arbitrary finding messages.

## 3. Opt into one PR comment

For a new integration, preview first:

```bash
agent-config-score init --pr-comment --dry-run
agent-config-score init --pr-comment
```

Review and commit `.agentconfigscore.json` and
`.github/workflows/agent-config-score.yml`. No GitHub API is called by `init`.
The generated file is identical to the tested copy-ready recipe, including:

- `pull_request`, not `pull_request_target`;
- explicit `pull-requests: write`, with credentials not persisted by checkout;
- same-repository PR comments only; fork PRs retain scanning and job summaries;
- one bot-owned marked comment, updated rather than appended on each run;
- pagination, output validation and cancelled/setup-failure handling;
- comment failures do not override the regression step's result.

Default `init` generates a workflow with read-only GitHub permissions, and
`--pr-comment` cannot be combined with
`--no-workflow`. Existing conflicting files are not overwritten. For an existing
setup, manually review the diff first; only use `--force` if you intend to replace
the generated targets. Do not install a second workflow alongside an existing
comment recipe. See [PR comment security and behavior](pr-comments.md).

The generated workflow currently uses the existing rolling `v0` Action ref.
Review/pin the tested revision suitable for your repository before committing;
the new source-only explanatory summaries require an Action revision containing
this change. Keep scanning dependencies separate from candidate repository code.

## Coverage is deliberately bounded

Path checks cover the [documented reference grammar](limitations.md#plain-prose-path-references),
not every possible reference, generated artifact, or shell command argument.
Prompt-injection flagging recognizes a narrow override grammar and certain
other cataloged risks; it does not inspect arbitrary retrieved web pages,
prove malicious intent, or enforce agent behavior. No new detection grammar is
introduced by the explanatory output. Read the [score limitations](limitations.md).

The maintained workflow tests use disposable synthetic repositories and a fake
GitHub client. They cover finding-to-fix-to-recheck and comment create/update
behavior, not a live user's adoption, a real deployment, or independent accuracy.
