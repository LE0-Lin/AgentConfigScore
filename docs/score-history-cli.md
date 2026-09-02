# Score History

AgentConfigScore can retain local score snapshots so teams can inspect changes in detected instruction risks over time. The score is not semantic quality certification; see the [score contract](limitations.md).

## Inspect local history

Local snapshots live at:

```text
.agentconfigscore/history/index.json
```

Use the CLI instead of reading the JSON by hand:

```bash
agent-config-score history
```

The text view shows the timestamp, score, grade, per-snapshot score change, commit, and an overall trend across all scored snapshots. By default it shows the newest 20 entries while calculating the overall trend from the complete local history.

```text
AgentConfigScore history

DATE                 SCORE  GRADE   CHANGE  COMMIT
2026-08-29 00:00:00     91      A        -  aaaaaaaaaaaa
2026-08-30 00:00:00     95      A       +4  bbbbbbbbbbbb

Trend: ↑ +4 overall across 2 scored snapshots
```

Useful options:

```bash
agent-config-score history --limit 5
agent-config-score history /path/to/repository
agent-config-score history --json
```

`--json` returns a stable object with two top-level fields:

- `summary` — snapshot count, scored count, first/latest score, total delta, and `up` / `down` / `flat` / `unknown` trend
- `history` — the visible snapshots after applying `--limit`

Missing or malformed local history is handled conservatively: the command reports no history instead of crashing. A non-positive `--limit` is treated as a usage error.

## Snapshot contents

Each local snapshot may record:

- commit identifier
- timestamp
- score
- grade
- scanned file count
- finding summary

The history loader tolerates partial entries so older snapshot formats remain readable.

## CI history

The reusable `.github/workflows/score-history.yml` workflow generates immutable GitHub Actions artifacts on default-branch updates. Each artifact contains the score metadata plus the JSON, HTML, and badge outputs for that run.

This CI artifact model intentionally does not write generated history files back into the repository. The local `history` command reads `.agentconfigscore/history/index.json`; CI artifacts remain immutable run evidence rather than silently mutating source control.

See [`score-history.md`](score-history.md) for workflow inputs, outputs, retention controls, monorepo usage, and the security model.
