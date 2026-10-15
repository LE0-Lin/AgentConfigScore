# Repository doctor

`agent-config-score doctor` checks whether a repository is ready to use AgentConfigScore consistently before you rely on it in CI.

```bash
agent-config-score doctor
```

The command is read-only and offline. It checks:

- whether `.agentconfigscore.json` exists and parses successfully;
- whether the config uses the canonical AgentConfigScore JSON Schema;
- whether supported coding-agent instruction files are discoverable;
- whether selected instruction sources can be safely resolved and read inside the scan root;
- whether the repository path index can be traversed without a filesystem error;
- whether the directory is inside a Git repository for `diff` workflows;
- whether `agent-config-score diff` can automatically resolve a safe local baseline;
- whether the standard GitHub Actions workflow exists and invokes AgentConfigScore correctly;
- whether any active suppression expires within the next 30 days.

When automatic baseline detection succeeds, doctor reports the selected ref, for example `main` or `origin/main`. If Git works but no safe default-branch baseline can be detected, doctor emits a warning. That warning is non-fatal because you can still pass an explicit baseline such as `agent-config-score diff origin/main`.

Warnings are advisory and keep exit status `0`. Concrete configuration or standard-workflow errors return a non-zero exit status.

The `repository-paths` check reports an error if index traversal fails, for
example because a source directory cannot be read. Fix the access problem before
scanning; an incomplete index must not be treated as a clean result or evidence
that a file is missing. Excluded dependency/admin trees are not traversed by this
index check. It checks path metadata only, not instruction quality, tracked-file
membership, or an atomic snapshot; access can change after the check completes.

The `instructions` check also reads each selected instruction source through the
scanner's regular-file/containment guard, without executing or semantically
evaluating its text. Invalid source links, unreadable instruction contents and an
invalid `.agentconfigscoreignore` become error checks rather than a successful
preflight. Internal file aliases are supported; child directory symlinks/junctions
are not traversed. See the [filesystem boundary and concurrency limits](limitations.md#instruction-file-filesystem-boundary).

For scripts and CI:

```bash
agent-config-score doctor --json
```

Example fields:

```json
{
  "ok": true,
  "warnings": 0,
  "errors": 0,
  "checks": [
    {
      "name": "baseline",
      "status": "pass",
      "message": "Automatic diff baseline resolves to main."
    }
  ]
}
```

A missing standard workflow is only a warning because repositories may intentionally use a custom workflow. If the standard `agent-config-score.yml` file exists but does not invoke AgentConfigScore, that is treated as an error because the expected integration is present but broken.
