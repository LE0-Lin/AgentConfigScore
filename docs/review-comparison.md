# Compare local lint with AI review

AgentConfigScore has not yet been evaluated head-to-head against AI review on an
independent held-out dataset. `scripts/run_review_comparison.py` provides an
offline workflow for running that comparison without calling a model API,
uploading files, or inventing results.

## Current status

- **Calibration set** ([report](../benchmarks/review-calibration-report.md)): 12
  synthetic development fixtures (11 provisionally resolved, 1 unresolved). ACS
  baseline is recorded (1 semantic miss); AI and hybrid columns remain `not run`.
- **Prospective candidates** ([prospective-review-v1](../benchmarks/prospective-review-v1/README.md)):
  5 pinned public root instruction files with bounded context exports. Next.js
  has since been reused for path-rule development
  ([development-reuse.json](../benchmarks/prospective-review-v1/development-reuse.json));
  human annotation ([human-pilot](../benchmarks/prospective-review-v1/human-pilot/README.md))
  and a matched comparative batch remain open.
- **Component path checks** ([path-audit-v1](../benchmarks/path-audit-v1/README.md)):
  provisional maintainer audits on names-only projections—useful for finding
  rule gaps, not a substitute for an adjudicated holdout.

## 1. Run the local baseline

```bash
python -m pip install -e .
python scripts/run_review_comparison.py score
```

Any active default `analyze()` finding counts as `review_needed: true` (no
custom policy or suppressions).

## 2. Export blinded packets for review

```bash
python scripts/run_review_comparison.py export \
  --output-dir .agent-config-score/review-run-01
```

This writes three local files:

- `review-packet.json`: neutral review prompt, opaque case IDs, and supplied
  files (no labels, rationales, source metadata, or tool findings).
- `predictions-template.json`: empty response schema for a fresh AI session.
- `human-annotation-template.json`: empty form for independent human reviewers.

Send only `review-packet.json` and `predictions-template.json` to a fresh AI
session with execution tools disabled. The response must preserve
`packet_sha256`, declare the actual model identifier in `reviewer`, set a unique
`run_id`, and return `true`, `false`, or `null` (insufficient context) for each
opaque ID:

```json
{
  "id": "opaque ID from the packet",
  "review_needed": true,
  "reason": "Brief explanation without quoting a credential."
}
```

## 3. Validate or score imported predictions

To check schema and packet integrity without labels:

```bash
python scripts/run_review_comparison.py validate \
  --packet .agent-config-score/review-run-01/review-packet.json \
  --predictions .agent-config-score/review-run-01/predictions.json
```

To score against a labeled corpus (outputs must be new files; pass multiple
`--predictions` flags to compare runs or measure repeat-run disagreement):

```bash
python scripts/run_review_comparison.py score \
  --predictions .agent-config-score/review-run-01/predictions.json \
  --output .agent-config-score/comparison-01.json \
  --markdown .agent-config-score/comparison-01.md
```

## Scoring rules

Evaluation is case-level (`review_needed`), not finding-level localization:

| Reference label | Decision | Outcome |
|---|---|---|
| Review needed | `true` | True positive |
| Review needed | `false` | False negative (miss) |
| Clean | `true` | False positive |
| Clean | `false` | True negative |
| Resolved label | Missing or `null` | Unreviewed (reduces coverage; suppresses headline P/R/F1) |
| Unresolved label | Any | Excluded from scoring |

- **Hybrid baseline:** three-valued OR (`tool OR ai`; clean + unknown stays
  unknown).
- **Optional usage metadata:** `input_tokens`, `output_tokens`,
  `elapsed_seconds`, and `cost_usd` stay `null` when unknown.
- **Fingerprints:** JSON reports record SHA-256 hashes for the corpus, blinded
  packet, tool/script source, and each prediction file.

## Building a real holdout

Use [benchmarks/review-calibration.json](../benchmarks/review-calibration.json)
as a schema template only. A manifest with `tier: "holdout"` must declare:

- `used_for_rule_development: false`
- `label_status: "adjudicated"`
- at least two distinct human `labelers` who labeled unseen, licensed snapshots
  independently before seeing tool or AI outputs.

Unlabeled collections use `tier: "candidate"` (`label_status: "unreviewed"`,
`labelers: []`) and can be exported and validated, but cannot be scored until
adjudicated labels are added.
