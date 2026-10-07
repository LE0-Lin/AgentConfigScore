# One pinned tool-side probe

**Current evidence: no completed real-snapshot scanner run.** Source archive
transfers and a read-only bare Git fetch repeatedly disconnected or timed out.
Offline fixture tests validate the workflow, not this real case's predictions.
[failures.json](failures.json) retains seven failed stages; none is a clean result.
No `report.json`, model comparison, or correctness score has been fabricated.

This research workflow checks the filesystem/scope part of evaluation. It does
not adjudicate the previous AI answer, compute correctness metrics, or tune any
scanner rule. Only the previously selected Next.js case is in scope; the five
parent cases and the original AI packet/response remain unchanged.

## Source integrity before findings

`scripts/run_pinned_tool_probe.py` can explicitly download the pinned public
source archive, or replay an already downloaded archive offline. It verifies:

- the original context corpus and one-case packet fingerprints;
- canonical Git directory objects, including Git's filename sorting/modes;
- complete archive membership and every file/link blob identity and size;
- all 11 supplied instruction/context file byte strings and their origins;
- captured known path facts against real filesystem objects.

The old recursive-tree response's `sha` was the queried commit ref, not the
canonical tree object. The first attempted probe stopped before downloading or
scanning. The original captured response remains unchanged for audit. The new
protocol anchors reconstructed directory objects to the canonical tree SHA
obtained from the pinned commit, and records these identities separately.

Interrupted and timed-out transfers were not scored. Before any scanner result,
the transport time budget was increased from 180 to 600 seconds; byte/member
limits, case selection, and scanner rules did not change. The
[pre-amendment transport protocol](../tool-probe-protocol.transport-initial.json)
is retained. This is disclosed exploratory method repair, not external
preregistration or evidence of accuracy.

There are no placeholder files. A successful snapshot must contain real tracked file bytes
and safe internal links. Executable modes and Git metadata are not installed;
ignored/generated/untracked files are not invented. Unsupported entries, unsafe
or unresolved links, case collisions, tampering, and resource limits fail closed.
Windows link separators are adapted without changing the verified Git blob.
No downloaded command, hook, dependency installer, or project test is run.

## Two scopes, not a matched accuracy comparison

The **native** run uses installed scanner behavior with default discovery. It may
read additional nested instructions absent from the AI packet. The **root scope**
run replaces only discovery inside the research process with `AGENTS.md`; it
leaves scanner rules, path checks, and the physical repository index unchanged.
That override is restored even if the scan fails. It is not an installed CLI
mode, and reference documents are not silently promoted to instruction files.

The root run still has a larger path index than the AI's bounded path facts.
The referenced text is physically present, but the scanner does not semantically
interpret it unless discovery selects it. These differences remain explicit:
`comparison_ready` is false and correctness metrics are null. A lint score is
not a correctness score, absence of findings is not proof of clean guidance,
and a differing flag is not yet a false positive or false negative.

Following [official OpenAI evaluation guidance](https://developers.openai.com/api/docs/guides/evaluation-best-practices),
human judgments must still calibrate automated decisions. No human labels,
hybrid result, independent user feedback, or new model run is supplied here.
Anyone exposed to either output cannot subsequently be a blind annotator of
this same case. Declare development reuse if findings later influence tuning.

## Explicit download or offline replay

From the project checkout, with `src` on `PYTHONPATH`:

```bash
python scripts/run_pinned_tool_probe.py \
  --output-dir .agent-config-score/tool-probe-new
```

Optional offline replay uses the same frozen tree and resource checks:

```bash
python scripts/run_pinned_tool_probe.py \
  --archive /absolute/path/to/source.tar.gz \
  --output-dir .agent-config-score/tool-probe-replay-new
```

Require new output paths. A failed transfer leaves a `.part` file and no completed
report; a partial source directory is also not a run. Do not relabel either as a
clean result. Source archives/snapshots remain local and ignored, not committed.
The local source sits under a `vendor` directory, which the unchanged scanner
already excludes when scanning this project's own workspace. Scanning the
snapshot itself still uses its normal repository-relative paths.
Only minimized report metadata and accompanying protocol belong in this folder.
Finding messages use fixed rule summaries rather than arbitrary source excerpts.

The original comparison runner still refuses to score candidate/context bundles.
A formal comparison requires a prospectively matched evidence/scope contract and
appropriate independent human reference annotation. This probe does not bypass
those gates.
