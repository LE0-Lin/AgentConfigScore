# Regression design lab

This runnable example explains two design choices: checking changes rather than
only numeric scores, and letting the reviewed baseline govern PR thresholds.
It uses **five synthetic, project-authored development scenarios**, not real-user
cases, an independent holdout or an AI comparison. No agent is run.

## Run from a source checkout

With Python 3.10+ and this repository available:

```bash
python -m pip install -e .
python scripts/run_regression_lab.py
```

No model API, network call or external repository is needed during the run. The
runner creates temporary before/after trees and invokes the real module CLI in
15 subprocesses. Commands inside fixture text are never executed. Source/runtime
identity must match across the runner and subprocesses. The script is a checkout
example, not a new installed subcommand or a feature published in v0.24.0.

To retain results, choose a **new** output filename:

```bash
python scripts/run_regression_lab.py --output .agent-config-score/design-lab-01.json
python scripts/run_regression_lab.py --json
```

Existing output files and file aliases are not overwritten. A failed save may
leave a new partial output; inspect before retrying. Exit `0` means the known
development expectations matched, `1` means a mismatch, and `2` means an
operational failure. These are lab exits, not estimates of detection accuracy.

## What the three columns mean

- **Baseline gate**: normal `compare`, with `max_drop: 0` and
  `fail_on_new_errors: true` in the baseline config.
- **Score-only**: the same comparison with `--no-fail-on-new-errors`. It still
  rejects a numeric score decrease. Findings remain visible; only error-based
  gating is disabled.
- **Candidate-threshold override**: intentionally pass the candidate's threshold
  values as trusted CLI overrides. This illustrates a caller trusting PR-authored
  thresholds. The normal tool never chooses them on its own. It is not a separate
  product, historical tool version or comparison of suppression policies.

## Retained observations

The [machine-readable run](observed.json) retained on 2026-11-02 records declared
tool version, tool-source fingerprint, normalized runner-source hash, scenario
hash, portable commands, actual exit codes and observed new error IDs. It uses
the runtime implementation at source revision
`4f928864f9d418887043908094a0083f1180f657`, with tool-source fingerprint
`bca1d4976d359c2f6e37a7068c077691461d8fc117d3df6a6ab3fdb5a10f82ef`.
The lab files themselves were added afterward in this development change.
Hashes bind recorded inputs/implementations; they do not authenticate execution
or certify evidence independence. Later reruns must retain their actual identity,
not relabel this observation as a newer tool.

| Synthetic scenario | Base -> head | Baseline gate | Score-only | Candidate-threshold override |
|---|---:|---|---|---|
| Unchanged instructions | 100 -> 100 | pass | pass | pass |
| Root instructions moved into a subtree | 100 -> 100 | block | pass | block |
| Exact directive reversed | 100 -> 100 | block | pass | block |
| Same-directory exact-text rename | 100 -> 100 | pass | pass | pass |
| Candidate weakens thresholds and adds a known risky command | 100 -> 82 | block | block | pass |

The scope-move row observes `instruction-file-removed`; the reversal row observes
`directive-polarity-flip`. Both show why a score delta alone can miss a declared
regression signal. The last row keeps `curl-pipe-shell` visible in every mode;
the intentionally weakened caller accepts it by changing its threshold decision.
The two passing controls show that this demonstration is not an always-block gate.

## What it does not establish

The scenarios were chosen because the implementation already supports them.
Five matching examples do not estimate real-world precision/recall, time saved,
agent behavior or user adoption. No AI baseline, independent human labels,
latency/cost comparison or counterfactual historical experiment was run.

File-removal and exact-polarity rules remain bounded heuristics. A same-directory
rename is an existing exact-text exception, not proof that different agents or
file formats have equivalent applicability. A legitimate scope migration can
need review or an expiring baseline-approved exception. A 100/100 passing result
can still contain harmful semantics outside the rule grammar. The candidate
override is deliberately weaker; an AI reviewer given both trees and policies
could also identify these examples. See [regression coverage](../../docs/regression-coverage.md)
and [limitations](../../docs/limitations.md).
