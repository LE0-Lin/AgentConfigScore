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
- whether the standard GitHub Actions workflow exists and invokes AgentConfigScore correctly;
- whether any active suppression expires within the next 30 days.

Warnings are advisory and keep exit status `0`. Concrete configuration or standard-workflow errors return a non-zero exit status.

For scripts and CI:

```bash
agent-config-score doctor --json
```

Example fields:

```json
{
  "ok": true,
  "warnings": 1,
  "errors": 0,
  "checks": [
    {
      "name": "config",
      "status": "pass",
      "message": ".agentconfigscore.json is valid (...)"
    }
  ]
}
```

A missing standard workflow is only a warning because repositories may intentionally use a custom workflow. If the standard `agent-config-score.yml` file exists but does not invoke AgentConfigScore, that is treated as an error because the expected integration is present but broken.
