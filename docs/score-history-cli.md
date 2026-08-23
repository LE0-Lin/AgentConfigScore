# Score History

AgentConfigScore keeps score snapshots so teams can observe instruction quality changes over time.

## Local history

After generating snapshots, history can be inspected from:

```
.agentconfigscore/history/index.json
```

Each entry records:

- commit identifier
- timestamp
- score
- grade
- scanned file count
- finding summary

## CI usage

The `score-history.yml` workflow can generate immutable history artifacts on default branch updates.

Recommended future integrations:

- trend reports
- score badges
- release quality summaries
- repository health dashboards
