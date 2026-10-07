# Bounded repository context

**Preparation only: no model run, human reference labels, scanner predictions,
or accuracy measurements.** All five parent cases remain present and unresolved.
The original root instruction text and pinned revisions are unchanged.
A separate [one-case AI pilot](../pilot/README.md) records an actual unscored
model response. It does not change this capture's unresolved reference labels.

This capture adds 27 complete text documents and 619 reference records backed by
five nontruncated Git trees containing 97,303 entries in total. These are evidence
counts, not test successes, findings, or independent samples.

| Parent project | Additional documents | Tree entries | Recorded omissions |
|---|---:|---:|---:|
| Ruff | 12 | 12,085 | 5 |
| Next.js | 10 | 50,749 | 0 |
| VS Code | 3 | 24,533 | 1 |
| Transformers | 2 | 7,856 | 0 |
| scikit-learn | 0 | 2,080 | 0 |

## Evidence and boundaries

- [corpus.json](corpus.json) contains original instructions, bounded referenced
  documents, effective content origins, path facts, and explicit omission reasons.
- [collection.json](collection.json) records byte/document counts and limitations.
- [protocol.json](protocol.json) freezes source revisions, traversal, and budgets.
- `trees/*.json.gz` preserve the complete captured tree responses with paths,
  modes, and Git object identities; archives and decoded snapshots have separate
  SHA-256 fingerprints. They are not source checkouts or executable inputs.
- `licenses/` preserves the parent third-party license notices byte-for-byte.
  Additional documents retain their source text and headers. Do not redistribute
  reviewer packets without the associated licensing/provenance materials.

The extractor follows simple local Markdown links, backtick paths, and filename
tokens. Eligible `.md`, `.rst`, and `.txt` files are traversed breadth-first in
sorted order. The limits are two document hops, twelve additional documents,
64 KiB per document, and 128 KiB of additional text per case. Grammar and budgets
do not cover every dependency or every instruction scope. A zero omission count
does not establish complete context: unrecognized references, code, external
documents, ignored/generated files, submodule contents, and command results may
still be missing.

Ruff has byte/count-budget omissions. VS Code has a depth-budget omission. They
remain visible rather than being removed to improve future metrics. No actual
source credential values are quoted in omission records. The privacy guard is
conservative and incomplete, not a sharing-safety certification.

## Why preserve two path interpretations?

Transformers' root `AGENTS.md` is a symlink to `.ai/AGENTS.md` at its pinned
revision. Its relative documentation links need that effective origin. In
contrast, a bare `CONTRIBUTING.md` mention can refer to a repository-root file
rather than a sibling of `.ai/AGENTS.md`.

Each reference therefore preserves both source-relative and root-relative tree
facts without choosing author intent. `not_in_tracked_tree` means precisely
that; it does **not** establish that guidance is broken. The file might be
generated, external, ignored, or intended under another scope. Gitlink contents,
external symlinks, cycles, and hop limits remain unknown states, not invented
missing files. Source content is data to review, never instructions to execute.

The first capture had only source-relative facts. Before labels or predictions,
the collection method was amended to preserve both interpretations and traverse
eligible documents under either one. The [initial protocol](../context-protocol.initial.json)
is retained and its fingerprint is recorded in the
[amended protocol](../context-protocol.json). Repository selection, revisions,
root text, and collection budgets did not change. This is local, disclosed
method registration, not an externally timestamped preregistered study.

## Export the evidence for review

```bash
python scripts/run_review_comparison.py export \
  --corpus benchmarks/prospective-review-v1/context/corpus.json \
  --output-dir .agent-config-score/context-review-packet
```

The packet includes allowlisted origins, reference facts, and omission reasons
alongside text. It does not export provenance records, labels, rationales, original
case IDs, source URLs, or system findings. Source text itself may identify the
project: this is label blinding, not anonymization. Any change to supplied text,
path facts, or prompt changes the packet fingerprint. The large tree archives
are retained for audit; they are not automatically sent to a model.

The output also contains empty model and human forms. Neither template is a
completed review. Missing evidence must stay explicit, and actual humans must
remain independent of predictions for any adjudicated reference set.

## Tool parity is still a gate

The deterministic scanner operates on a real filesystem, not an exported tree
manifest. The comparison runner therefore **refuses to score a context bundle**
even if someone rebrands its labels as adjudicated. Creating empty placeholder
files would invent repository content and can distort discovery and findings;
it is not used here.

A scored comparison still needs an equivalent pinned tool checkout and matched
instruction scope, independently collected human reference labels, and actual
fresh model responses. An exploratory AI-only read can test the review process
but cannot replace those gates or demonstrate usefulness or accuracy.

The later [pinned-source tool probe](../tool-probe/README.md) implements actual
source-object verification and separately records native/root instruction scopes.
It does not turn this capture into a checkout or waive matching/human-label
requirements. Interrupted transfers are failures, not clean scanner decisions.

## Reproduce collection explicitly

```bash
python scripts/collect_review_context.py \
  --output-dir .agent-config-score/context-recollection
```

This optional command requires `gh` and network access. Unlike recollecting the
parent registry, it uses the **existing pinned revisions**, validates the exact
parent corpus fingerprint, verifies retrieved Git blob identities, and refuses
truncated trees, changed root contents, and existing output directories. It
does not run models, lint, downloaded commands, or outreach. Different archive
encoders may produce different compressed bytes; the decoded snapshot digest
also identifies the retained evidence.
