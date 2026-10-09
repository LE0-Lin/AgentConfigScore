# One pinned tool-side probe

**Current evidence: one completed real-snapshot scanner probe, unscored.**
[report.json](report.json) retains the actual Linux replay on 2026-10-09 using
the unchanged [frozen protocol](replay-protocol.json) and compatible checkout
`1d7acc812e1a6e568317d6fe00bf366ef2a81338` (package version **0.22.0**, not the
published 0.23.0). [replay-20261009.json](replay-20261009.json) binds the report
and records transport/environment repair. The original seven stages in
[failures.json](failures.json) remain unchanged; new failures are also retained.
No model comparison, reference label or correctness score is supplied.

## Retained observation, not confirmed defects

The 51,988,413-byte archive matched all 50,749 tracked entries: 33,876 regular
files, 16,831 directories and 42 internal symlinks, with 158,608,765 verified
blob bytes. The run checked all 11 supplied text files and 420 physical path
facts; 36 unknown facts were not asserted. Source commands were never executed.

| Instruction scope | Files | Active findings | Lint score |
|---|---:|---:|---:|
| Native discovery | 27 | 9 | C 76 |
| Research-only root `AGENTS.md` | 1 | 9 | C 76 |

Both scopes retained eight `dead-path` signals and one `context-large` warning.
These counts are **not eight verified broken paths** or a confirmed project bug.
The root instruction's earlier AI concern and these rule signals can flag the
same case for different reasons; that is not finding-level agreement or recall.
The larger filesystem index and absent independent reference labels still
prevent a matched correctness comparison.

The latest Python transfer ended with `IncompleteRead`. A separately bounded
curl transfer completed, then the Windows replay stopped before scanning:
the captured absence fact for `README.md` conflicted with Windows resolving it
to the tracked lowercase `readme.md` symlink. Replaying that same archive in a
new native Linux directory satisfied the unchanged evidence checks. Neither
the path facts, source names nor scanner rules were loosened to obtain a result.
Host-dependent behavior matters; this is not an OS-invariant defect judgment.

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
Use a case-sensitive filesystem when reproducing this retained Linux case.
An incompatible host must remain a failed preparation, not a clean prediction.

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

The retained protocol freezes **all product source**, not just scoring rules.
Later CLI/packaging fixes on `main` intentionally invalidate its tool fingerprint.
Replay the original protocol from the recorded compatible checkout
`1d7acc812e1a6e568317d6fe00bf366ef2a81338`; do not rewrite the retained fingerprint
to make newer code appear to be the registered tool. Synthetic unit fixtures
test current helper behavior separately and are not actual public-case runs.

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
