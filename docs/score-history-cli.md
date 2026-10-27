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

An absent local index reports no history with exit `0`. **Unreleased source
builds no longer treat damaged or unreadable history as an empty list**: they
return operational exit `2`, leave stdout empty (including `--json`), and leave
the index unchanged. `--limit` controls display only, not validation: a damaged
older entry outside the visible window still fails. A non-positive `--limit`
remains an invocation error. These stricter behaviors are not in v0.24.0.

## Snapshot contents

Each local snapshot may record:

- commit identifier
- timestamp
- score
- grade
- scanned file count
- finding summary

The history loader tolerates partial entries so older snapshot formats remain
readable. Missing or `null` scores are unscored; old entries do not acquire a
current tool identity. Unknown metadata is retained, not authenticated or
semantically validated. Finite fractional scores from older/custom records
remain readable; the scanner itself emits integer scores.

## Invalid history and recovery (unreleased)

The index must be UTF-8 JSON containing an array of snapshot objects. Source
builds reject invalid JSON, non-object rows, duplicate decoded member names
(including equal-valued repeats and escaped spellings), non-finite numbers
(`NaN`, `Infinity`, `-Infinity`, overflowed floating-point values), and present
scores that are not numeric values from 0 to 100 or `null`. Booleans are not
scores. Rows are not silently dropped. An explicit empty array remains valid.

History diagnostics do not echo raw record contents, member names or underlying
filesystem error details. The selected index and its two history-store parent
directories must use ordinary files/directories, not symlinks or Windows reparse
paths. A dangling link is an error, not missing history. An explicitly selected
repository root alias remains allowed; these checks are not a filesystem sandbox
or protection against arbitrary concurrent path changes.

On an error, back up `.agentconfigscore/history/index.json` outside the history
store, inspect it locally and repair it or restore a known-good copy. For a
linked store, migrate to a regular local file/directory deliberately. Do not
replace the index with `[]` just to hide the error; that discards evidence. No
automatic reset, repair, import or network upload is performed. Recheck with
`agent-config-score history --json` after repair. An unreadable file can require
permission repair before it can be backed up.

The Python `append_snapshot` helper validates the full existing store before
retention, validates the proposed snapshot and serializes it before creating a
temporary file. It writes/flushes/syncs a complete file beside the index and then
uses `os.replace`, instead of truncating the old index. Tested write, sync and
replacement failures preserve the previous bytes; serialization failures do not
create a new store. Temporary files are cleaned on ordinary failures when
permissions allow. A process crash or cleanup failure can leave `.index-*.tmp`
files; inspect and back them up before manually removing them.

This is not a concurrent-writer transaction or a power-loss durability guarantee:
callers must serialize appends, and network filesystem behavior can differ.
Replacement changes file identity and may change ACLs or extended metadata;
ordinary mode bits are copied where supported. There is no writer lock or
directory `fsync`. Successful retention intentionally keeps only the newest
`limit` records (default 100). `load_history`/`append_snapshot` now raise
`HistoryError` (a `ValueError`) rather than resetting a damaged store; direct
callers should handle it and preserve the original data.

The local CLI only reads snapshots. Normal scans do not automatically call the
Python append helper, and a successful history read does not certify that the
records are authentic, comparable across tool/policy versions, or an independent
measure of accuracy or agent safety.

## CI history

The reusable `.github/workflows/score-history.yml` workflow generates immutable GitHub Actions artifacts on default-branch updates. Each artifact contains the score metadata plus the JSON, HTML, and badge outputs for that run.

This CI artifact model intentionally does not write generated history files back into the repository. The local `history` command reads `.agentconfigscore/history/index.json`; CI artifacts remain immutable run evidence rather than silently mutating source control.

See [`score-history.md`](score-history.md) for workflow inputs, outputs, retention controls, monorepo usage, and the security model.
