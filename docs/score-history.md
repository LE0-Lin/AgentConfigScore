# Score history snapshots

AgentConfigScore can record an immutable score snapshot for every default-branch update without writing generated files back to the repository.

The reusable workflow lives at:

```text
LE0-Lin/AgentConfigScore/.github/workflows/score-history.yml@v0
```

## Quick start

Create `.github/workflows/agent-config-score-history.yml` in your repository:

```yaml
name: agent-config-score-history

on:
  push:
    branches:
      - main
  workflow_dispatch:

permissions:
  contents: read

jobs:
  snapshot:
    uses: LE0-Lin/AgentConfigScore/.github/workflows/score-history.yml@v0
```

Change `main` if your repository uses a different default branch.

The workflow needs no secrets, API keys, or write permission. It checks out the caller repository, runs AgentConfigScore, and uploads one commit-keyed GitHub Actions artifact.

## Artifact contents

Each artifact is named `agent-config-score-<commit SHA>` and contains:

| File | Purpose |
|---|---|
| `snapshot.json` | Compact history record with commit metadata and score metrics |
| `report.json` | Full machine-readable AgentConfigScore report |
| `report.html` | Self-contained human-readable report |
| `badge.svg` | Badge snapshot for that commit |

A `snapshot.json` record looks like:

```json
{
  "schema_version": 1,
  "repository": "owner/repository",
  "commit": "0123456789abcdef...",
  "ref": "refs/heads/main",
  "run_id": "123456789",
  "run_attempt": 1,
  "generated_at": "2026-08-21T17:28:44+00:00",
  "tool_version": "0.14.0",
  "score": 96,
  "grade": "A",
  "files": 3,
  "estimated_tokens": 1240,
  "duplicate_ratio": 0.04,
  "active_findings": 1,
  "suppressed_findings": 0
}
```

This makes score history easy to inspect manually or consume later with scripts without treating HTML or an SVG badge as the source of truth.

## Inputs

| Input | Default | Meaning |
|---|---|---|
| `path` | `.` | Repository path to score |
| `python_version` | `3.12` | Python version used by the workflow |
| `retention_days` | `30` | Artifact retention from 1 to 90 days |
| `tool_ref` | `v0` | AgentConfigScore ref installed by the workflow |

Example with a longer retention period and a monorepo path:

```yaml
jobs:
  snapshot:
    uses: LE0-Lin/AgentConfigScore/.github/workflows/score-history.yml@v0
    with:
      path: services/api
      retention_days: 90
```

## Outputs

The reusable workflow exposes:

| Output | Meaning |
|---|---|
| `score` | Numeric AgentConfigScore score |
| `grade` | Letter grade |
| `artifact-id` | GitHub Actions artifact ID |
| `artifact-url` | URL for the uploaded artifact |

These outputs can be consumed by a later job when a repository wants to build its own notification, dashboard, or reporting layer.

## History semantics

This feature intentionally uses GitHub Actions artifacts instead of committing generated files back to the repository.

That keeps the default permission model read-only and avoids bot commits, branch churn, and merge conflicts. Every successful run produces a new immutable commit-keyed snapshot, so the Actions run history becomes the index of score snapshots.

Artifacts are **not permanent storage**. GitHub deletes them after the configured retention period, subject to repository and organization retention limits. If you need permanent public history, consume `snapshot.json` from the workflow and publish it to storage you control.

## Relationship to the regression gate

Score history and regression gating serve different purposes:

- the pull-request regression gate answers **“did this change make agent instructions worse?”** and can block a PR;
- the score-history workflow records **“what was the score at this commit?”** and does not fail merely because the score is low.

The history workflow therefore overrides any absolute `fail_under` policy to `0` while generating the snapshot. Configuration parsing and scanner failures still fail the workflow because a snapshot that could not be computed should not be recorded as valid history.

## Security model

The reusable workflow declares only:

```yaml
permissions:
  contents: read
```

It does not request repository write access, does not upload repository content to a hosted analysis API, and does not require an LLM or external API key. The only uploaded material is the generated GitHub Actions artifact inside the caller repository's Actions storage.
