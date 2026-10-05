# One fresh-context AI pilot

**One actual AI response, no correctness score.** This is an exploratory review
of one publicly collected case, not real user feedback, a held-out study, or an
AI-versus-tool comparison. Human reference labels remain unresolved.

The user explicitly authorized one fresh-context sub-agent. The
[pilot protocol](../pilot-protocol.json) selected the first registry case with
additional context fitting the declared 64 KiB text / 160 KiB packet limits.
Ruff exceeded those limits; Next.js was the first eligible case. Selection was
based on resource size, not outputs. All five cases remain in the parent corpus.

## Retained artifacts

- [review-packet.json](review-packet.json): one opaque-ID case, the neutral
  prompt, unchanged instruction/context text, and bounded path facts.
- [predictions-template.json](predictions-template.json): the original empty
  response shape; this remains empty and is not the actual run.
- [preparation.json](preparation.json) and [protocol.json](protocol.json):
  pre-run resource decisions and packet/corpus/protocol fingerprints.
- [response.json](response.json): the actual sub-agent's final JSON, retained
  without changing its decision or reason.
- [validation.json](validation.json): response-format/input integrity checks,
  **not** semantic validation or accuracy metrics.
- [run.json](run.json): interface, fresh-context settings, unknown model/cost
  metadata, observation times, and the remaining evidence boundaries.
- [license notice](licenses/vercel--next.js.txt): required accompanying source
  attribution. Source provenance remains in the parent context corpus.

The reviewer was launched with `fork_turns="none"`; project history, labels,
scanner rules, and tool reports were not included in its task. It was instructed
to read only the packet and response template and not execute commands, fetch
URLs, edit files, or contact anyone. Tools were not technically disabled, so this
is not a capability-sandbox guarantee or an independently audited execution log.
The interface did not expose an exact model/version; that field stays unknown.
Token usage, API cost, and model latency are unknown, not zero. The timestamps
are parent observations, not a latency benchmark.

## What the response says, and does not establish

The AI returned `review_needed: true`, citing `AGENTS.md` lines 249 and 252:
forced scratch-worktree removal and cleanup that also runs on failure. Those
locations were checked against the supplied text. But lines 242-244 explicitly
describe a **throwaway** worktree intended to protect the user's checkout.

Whether preserving failed temporary edits is needed depends on the intended
workflow. The response is a review suggestion, not a confirmed project defect.
There is no human reference decision and no equivalent tool-checkout result;
calling it a true positive, a scanner miss, or evidence that AI is superior would
invent measurements. The project-agent note in `run.json` is also an AI-authored
interpretation, **not** human adjudication. No new rule or external issue was
created from this result.

This process follows the principle of calibrating model judgment against real
human judgments rather than treating it as ground truth. See
[official OpenAI evaluation guidance](https://developers.openai.com/api/docs/guides/evaluation-best-practices).

Because the exploratory answer is now visible, anyone exposed to it must not
later be described as a blind human labeler for this same case. If it influences
rule or prompt tuning, declare that reuse and move the case to development
evidence. A genuine comparative study still requires appropriate independent
reference annotation and matched tool evidence.

## Validate without pretending to score

```bash
python scripts/run_review_comparison.py validate \
  --packet benchmarks/prospective-review-v1/pilot/review-packet.json \
  --predictions benchmarks/prospective-review-v1/pilot/response.json
```

This verifies the packet fingerprint, opaque case IDs, prediction schema, and
coverage without running lint or using reference labels. `metrics` stays null.
Optional outputs must be new files.

```bash
python scripts/prepare_review_pilot.py \
  --output-dir .agent-config-score/pilot-preparation-replay
```

This second command reproduces preparation locally. It does **not** start a model
or reproduce the actual response, and it is not authorization for more agents.
