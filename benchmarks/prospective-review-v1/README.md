# Prospective review candidates v1

**Status: five unreviewed public instruction snapshots, not a completed holdout
or AI comparison.** The original collection has no scanner predictions, human
reference labels, user feedback, or accuracy estimates. A separate
[single-case exploratory pilot](pilot/README.md) now retains one actual
fresh-context AI response, unscored and not substituted for human labels.

A subsequent [bounded-context capture](context/README.md) adds 27 documents,
complete pinned Git trees, symlink origins, and source-relative/root-relative
path facts. It retains all five cases and all missing-context limitations.
Equivalent tool-checkout evidence, human labels, and a comparative model batch remain outstanding.

The [registered protocol](protocol.json) was written before downloading the
instruction contents or inspecting predictions. It names twelve repositories;
five met the collection conditions and seven were excluded. This is a small
convenience registry, not random sampling. A prior filename-only search confirmed
Ruff's root `AGENTS.md`; that pilot observation is disclosed in the protocol.
These repository names did not appear in tracked development fixtures when the
registry was chosen. That check cannot establish absence from all prior informal
work, from a model's training data, or from other reviewers' experience.
Registration here means a locally written frozen protocol, not an independently
timestamped external preregistration.

## Retained candidates

Each input is the entire root `AGENTS.md`, unchanged, with a pinned revision,
exact line range, UTF-8 byte fingerprint, and third-party license notice:

| Project | Lines | Declared repository license | Pinned source |
|---|---:|---|---|
| Ruff | 222 | MIT | [AGENTS.md](https://github.com/astral-sh/ruff/blob/1df6db3e463ffa1b587dcf47f25360d40389b0f7/AGENTS.md) |
| Next.js | 520 | MIT | [AGENTS.md](https://github.com/vercel/next.js/blob/ba80ee48fc319735151c3ad6d9bb9a8180c9f09e/AGENTS.md) |
| VS Code | 5 | MIT | [AGENTS.md](https://github.com/microsoft/vscode/blob/b993b3bce18ed4816ff7076e7c33d0fbf3e01cda/AGENTS.md) |
| Transformers | 40 | Apache-2.0 | [AGENTS.md](https://github.com/huggingface/transformers/blob/469230357aab0f2b303b0d638c1f8d06edb14184/AGENTS.md) |
| scikit-learn | 28 | BSD-3-Clause | [AGENTS.md](https://github.com/scikit-learn/scikit-learn/blob/a442e4bb39551feb7b0af4c00075e2cb91cf9b77/AGENTS.md) |

[collection.json](collected/collection.json) retains all twelve repository
decisions, including excluded inputs. Six had no root file at the pinned
revision. The GitHub license endpoint reported `NOASSERTION` for uv, outside the
registered allowlist; this is **not** a claim that uv has no open-source license.
No replacements were sampled, no instructions were mutated, and no examples were
chosen because of tool results. Preserve the [third-party license
notices](collected/licenses) when redistributing these snapshots. These notices
govern the collected materials, not AgentConfigScore's own source license.

The source files passed only a conservative credential-shaped privacy exclusion
guard. This does not certify that the contents are safe to share. The collector
does not execute their commands, contact authors, or run the scanner/model.

## What is deliberately missing

In the original `collected/` corpus, only root instruction files were collected. Repository trees, linked documents,
code, nested instruction scopes, and command results are absent. A short file
that delegates to another document is retained rather than silently replaced.
Do not label omitted local paths as broken or treat absent context as a clean
bill of health. No claims about actual project defects are made here.

Before scoring, assemble relevant evidence from these **same pinned revisions**
for both reviewers, including delegated instructions and enough path context to
check a claimed missing file. Freeze a new evidence packet and its fingerprint.
If a path/context claim still cannot be decided, retain `unresolved`. A corpus
owner must not simply rebrand these snapshots as adjudicated holdout data.

Do not run the default scanner against these deliberately incomplete snapshots
and present its `dead-path` output as real-project findings. Likewise, do not
exclude rules after seeing which outputs make a comparison look favorable.
Any narrower task needs its own predeclared rubric and matching tool decision
rule before inspecting predictions.

## Export preparation materials

From a checkout with AgentConfigScore installed:

```bash
python scripts/run_review_comparison.py export \
  --corpus benchmarks/prospective-review-v1/collected/corpus.json \
  --output-dir .agent-config-score/prospective-review-v1-packet
```

This creates an opaque-ID review packet, an empty model-response template, and
an empty human-annotation template. No labels, rationales, provenance fields,
or system results are exported. Source text can identify its project; this is
**label blinding**, not anonymization or guaranteed protection against prior
knowledge. Retain license/provenance materials separately; the reviewer packet
is not a standalone licensed redistribution bundle.

The annotation template is not an importer or an adjudicator. Give independent
copies to actual human reviewers; record their identifiers, decisions,
rationales, and missing-context notes, retaining originals before resolving
disagreements. Do not count an AI response as a human label, or assume that two
copies of an empty template mean two people have reviewed the data. If only one
human is available, describe the work as a provisional pilot, not an independent
adjudicated reference set.

The candidate corpus declares `tier: "candidate"`, `label_status: "unreviewed"`,
`labelers: []`, and only unresolved labels. **The scoring command refuses this
tier**, even if a caller attempts to inject a resolved label. The exporter does
not submit data to an AI service or claim that a review has happened.

## Recollecting is not replaying

The committed snapshots can be exported fully offline. The optional collector
requires the existing `gh` CLI and explicitly uses the network:

```bash
python scripts/collect_review_candidates.py \
  --output-dir .agent-config-score/prospective-review-v1-recollection
```

It pins each selected repository's default-branch head **at collection time**.
Running it later can yield different revisions or inclusion decisions. Such an
output is a new collection, not a reproduction of this frozen corpus. Existing
directories are refused. Transport/authentication failures stop collection
rather than becoming exclusions or clean cases.

## Next evidence gates

1. Supply and freeze shared context; keep scanner rules unchanged.
2. Obtain independent human annotations and adjudicate them without predictions.
3. Record an actual fresh AI run, model/interface/settings, failures, time, and
   cost where available; unknown values stay unknown.
4. Compare default tool, AI, and the declared OR hybrid using the
   [comparison protocol](../../docs/review-comparison.md). Keep all disagreements.
5. If there are no reference-positive cases, recall is not estimable. Five
   convenience-sampled repositories cannot establish broad accuracy, superiority
   over AI, or real user adoption. Publish the limitation rather than inventing
   positive examples or counting mutations as fresh real samples.

If any input or result guides rule/prompt tuning, record that reuse and move it
to development evidence; collect a new holdout for the next evaluation.
