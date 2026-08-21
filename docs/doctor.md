# Repository doctor

`agent-config-score doctor` checks whether a repository is ready to use AgentConfigScore consistently before you rely on it in CI.

```bash
agent-config-score doctor
```

The command is read-only and offline. It checks:

- whether `.agentconfigscore.json` exists and parses successfully;
- whether the config uses the canonical AgentConfigScore JSON Schema;
- whether supported coding-agent instruction files are discoverable;
- whether the directory is inside a Git repository for `diff` workflows;
- whether `agent-config-score diff` can automatically resolve a safe local baseline;
- whether the standard GitHub Actions workflow exists and invokes AgentConfigScore correctly;
- whether any active suppression expires within the next 30 days.

When automatic baseline detection succeeds, doctor reports the selected ref, for example `main` or `origin/main`. If Git works but no safe default-branch baseline can be detected, doctor emits a warning. That warning is non-fatal because you can still pass an explicit baseline such as `agent-config-score diff origin/main`.

Warnings are advisory and keep exit status `0`. Concrete configuration or standard-workflow errors return a non-zero exit status.

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
