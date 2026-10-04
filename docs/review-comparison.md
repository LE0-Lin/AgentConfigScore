# Compare local lint with AI review

AgentConfigScore has not established that it is more accurate than asking an AI
to review an instruction file. Its maintained rule contracts are development
evidence, not a head-to-head evaluation. This workflow makes that comparison
possible without a model API dependency, automatic uploads, or fabricated model
results.

**Status: no independent AI comparison has been completed.** The bundled twelve
inputs are synthetic calibration fixtures with provisional project-authored
labels. They reuse known cases and must not be called held-out or real user data.

A separate [prospective candidate collection](../benchmarks/prospective-review-v1/README.md)
now retains five pinned public root instruction files, a predeclared twelve-repository
registry, every exclusion, and third-party license notices. It is **unreviewed
preparation material**, not a completed study. Repository context, human reference
labels, and actual independent AI runs still need to be supplied.

## Run the local baseline

From a repository checkout with the package installed:

```bash
python -m pip install -e .
python scripts/run_review_comparison.py score
```

The baseline treats any active default `analyze()` finding as a review signal,
not as proof of a security defect. It does not apply custom policies or
suppressions. No numeric score threshold defines the reference label.

The [committed calibration report](../benchmarks/review-calibration-report.md)
shows one known semantic miss on eleven provisionally resolved cases. One
ambiguous case is excluded because its reference label is unresolved. AI and
hybrid results say **not run**, not zero or perfect accuracy.

## Export the same inputs for blinded review

```bash
python scripts/run_review_comparison.py export \
  --output-dir .agent-config-score/review-run-01
```

This creates three local files:

- `review-packet.json`: a neutral review prompt, opaque case IDs, and the supplied
  files. No reference labels, rationales, source metadata, original case names,
  categories, or tool findings are exported.
- `predictions-template.json`: the response shape with empty reviewer/run IDs
  and null decisions. The unchanged template cannot be presented as a completed
  model run.
- `human-annotation-template.json`: an empty reference-label form for actual
  independent human reviewers, with rationale and missing-context fields. It
  is not an AI prediction, completed human annotation, or automatic adjudicator.

Review the packet before sharing. Only send the packet and template to a fresh
AI session, not the labeled corpus, this guide's results, or a tool report.
The packet's prompt instructs the reviewer to assess file contents as data, not
obey embedded instructions. No prompt is a security guarantee; do not enable
execution tools for this experiment. The exporter does not upload anything.
For private repositories, obtain any required permission before sharing; redact
sensitive material and reassess labels consistently for **both** reviewers.

The model must return JSON with the same `packet_sha256`, a declared actual
model/version in `reviewer`, a unique `run_id`, and predictions such as:

```json
{
  "id": "opaque ID from the packet",
  "review_needed": true,
  "reason": "Brief explanation without quoting a credential."
}
```

Use `false` for no concrete review issue, and `null` for insufficient context or
an abstention. A string such as `"false"` is invalid. Unknown and duplicate IDs
are rejected. A changed prompt or input packet invalidates the import.
Record the model identifier actually available; do not invent a hidden model
snapshot. Preserve original responses and record interface, date, and model
settings when available. The harness cannot authenticate who produced a file.

## Import and compare

Save the complete JSON response as `predictions.json`, then run:

```bash
python scripts/run_review_comparison.py score \
  --predictions .agent-config-score/review-run-01/predictions.json \
  --output .agent-config-score/comparison-01.json \
  --markdown .agent-config-score/comparison-01.md
```

All output paths must be new. Existing files are never overwritten. Multiple
`--predictions` arguments compare multiple runs. Repeated runs with the same
declared reviewer identifier receive a disagreement count and explicit coverage;
different model identifiers are not mixed into a repeatability measure.

## What is measured

The reference task is **case-level maintainer review needed**, not general prompt
quality, exploitability, or exact issue localization. A correct flag for one
problem can conceal another missed problem in that case. Use focused cases and
inspect per-case results; do not equate these numbers with finding-level recall.

| Reference label | Decision | Count |
|---|---|---|
| Review needed | `true` | True positive |
| Review needed | `false` | Miss / false negative |
| Clean | `true` | False positive |
| Clean | `false` | True negative |
| Resolved label | Missing or `null` | Unreviewed; never implicitly clean |
| Unresolved reference label | Any | Explicitly excluded from correctness scoring |

Missing answers and abstentions reduce coverage. If any resolved case is
unreviewed, that run has **no headline precision, recall, F1, or accuracy**. Counts
remain visible so dropping difficult cases cannot improve a completed metric.
Zero detected positives do not become perfect precision; undefined ratios are
null. Category breakdowns are included in JSON; Markdown lists disagreements and
unreviewed cases.

The hybrid baseline is an OR, not an AI adjudication of scanner findings:
either reviewer flagging a case makes it reviewable; a clean tool decision plus
an unknown AI decision stays unknown. Combining flags can increase false
positives. The harness does not silently let either reviewer overrule the other.

Optional prediction `usage` fields are `input_tokens`, `output_tokens`,
`elapsed_seconds`, and `cost_usd`. Unknown values remain null, not free or instant.
These are self-reported metadata, not measured API billing or end-to-end workflow
latency. Repeated accuracy or speed claims need actual controlled measurements.

JSON reports bind the full labeled corpus, blinded packet/prompt, tool and metric
source, and each imported response with separate SHA-256 fingerprints. Label
corrections change the corpus fingerprint without changing the blinded packet.
The Python version is also recorded. Reports omit input contents and model
explanations; locally retained source artifacts still need privacy review.

## Build a real holdout before drawing conclusions

Use [the calibration manifest](../benchmarks/review-calibration.json) as a format
example, **not** as an independent dataset:

1. Define the review rubric and sampling method before inspecting predictions.
   Include genuinely clean inputs, concrete risks, semantics, and ambiguous
   context. Preserve relevant repository files so both reviewers get the same
   evidence; do not penalize missing context as if it were supplied.
2. Collect unseen, licensed or authorized snapshots/excerpts. Record provenance
   and pinned revisions, and group related examples by repository or mutation
   family. Do not split variants of the same example across development and
   holdout data, or choose only cases where one reviewer wins.
3. Have at least two reviewers label independently without seeing either
   system's output, then adjudicate disagreements. Keep genuinely unresolved
   labels unresolved. Record reviewer identifiers and annotation rationales.
4. Freeze the corpus and prompt, then run both systems. Retain all responses,
   failures, abstentions, and repeat runs, including unfavorable results.
5. If the inputs or results guide subsequent rule/prompt tuning, mark them
   development/calibration data and evaluate on a new holdout.

A manifest with `tier: "holdout"` must declare `used_for_rule_development: false`,
`label_status: "adjudicated"`, and at least two distinct labelers. The loader
checks these declarations, rejects duplicate input snapshots, and validates
portable in-repository fixture paths. **It cannot prove independence, correct
labels, provenance, licensing, or reviewer identity.** Metadata is not evidence
of a study having happened. Small correlated samples also do not support a
general real-world accuracy claim.

Unlabeled preparations can instead use `tier: "candidate"`,
`used_for_rule_development: false`, `label_status: "unreviewed"`, `labelers: []`,
and only `unresolved` labels. They may be exported but **cannot be scored**.
This records work still missing without inventing reviewers or reference labels.

This is a repository research script, not a new installed CLI subcommand. The
deterministic scanner, report schema, runtime dependencies, and existing rule
contracts are unchanged.
