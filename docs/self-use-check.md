# Can ACS catch problems in its own instructions?

We tested the published **v0.26.2** wheel against disposable copies of this
repository at `b782906aeea0dbfc3e99d1d7e95a81a699741c97` (without executing any
commands written in the instruction files). The untouched repository scores
**100** across its five supported instruction files (`AGENTS.md` plus the
Claude, Cursor, Copilot, and Gemini examples). Full raw outputs are retained in
[evidence/self-use-0262.json](evidence/self-use-0262.json).

## Fixes shipped in v0.27.0

Two of the original high-score misses below were fixed in v0.27.0. A matched
comparison on the same archive (`1cec1aafe1d02259d94df5d785b604deda895de2`) is
retained in [evidence/self-use-prose-comparison.json](evidence/self-use-prose-comparison.json):

| Known probe | Published v0.26.2 | v0.27.0+ | Compare exit |
|---|---:|---:|---:|
| Production database deletion with explicit approval bypass | 100 | 85 (`deletion-approval-bypass`) | 1 |
| Chinese instruction to falsely report passing tests | 100 | 88 (`false-success-report`) | 1 |
| Vague filler only (`"Do a good job."`) | 100 | 100 | 0 |

These fix known development cases; vague or arbitrary prose can still score 100.

## Original published-wheel results (v0.26.2)

| Change to root `AGENTS.md` | Scan score | Scan exit | Compare exit |
|---|---:|---:|---:|
| No change | 100 | 0 | 0 |
| Recommend `rm -rf build` | 89 | 1 | 1 |
| Prohibit `rm -rf build` | 100 | 0 | 0 |
| Link to a nonexistent guide | 96 | 0 | 1 |
| Fix link to existing user guide | 100 | 0 | 0 |
| Require claiming failed tests passed | 88 | 1 | 1 |
| Recommend piping a remote installer into `bash` | 82 | 1 | 1 |
| Recommend deletion and weaken candidate policy | 89 | 0 | 1 |
| Empty the root instruction file | 70 | 1 | 1 |

A broken link only deducts 4 points, so a standalone scan with a floor of 90
still exits `0` at 96—**use baseline comparison (`diff` / `compare`) for PR
gates**, where the baseline's zero-drop and new-error rules reject both the
broken link and a candidate that tries to weaken its own policy.

### Original limitation probes (v0.26.2)

| Instruction change | Score | Gate |
|---|---:|---|
| Replace root guidance with `"Do a good job."` | 100 | Pass |
| Authorize removing the production database without confirmation (prose, no shell command) | 100 | Pass |
| Require falsely claiming tests passed, written in Chinese | 100 | Pass |

The separate, unscored `guardrails` check also flagged that our original root
`AGENTS.md` lacked explicit deletion/overwrite approval wording, which we added
as part of this maintenance pass.

## Reproduce locally

Install the target wheel in an isolated venv, then run from a local checkout:

```bash
python scripts/run_self_acceptance.py --python /path/to/venv/bin/python \
  --ref b782906aeea0dbfc3e99d1d7e95a81a699741c97 --output self-use-new.json
```

On Windows, pass `Scripts/python.exe`. `--ref HEAD` tests the current committed
snapshot (ignoring uncommitted edits), and `--output` must be a new file.

For v0.27.0+, pass `--require-current-fixes` to enforce the 12 known contracts
(including the database-bypass, Chinese false-passing, and inline-link example
cases) while keeping the vague-filler probe descriptive. CI and release
acceptance run this profile on Linux, Windows, and macOS.

This is maintainer self-acceptance on our own repository—not an independent
accuracy benchmark or external adoption metric. See [limitations.md](limitations.md)
and [maintainer-workflow.md](maintainer-workflow.md).
