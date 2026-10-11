# Path-reference development check

This is **development-reused, AI-authored maintenance evidence**, not an
independent holdout, human annotation, real user feedback or AI comparison.
The [reuse record](../../development-reuse.json) identifies the eight instruction
lines and three mechanisms that informed the fixes. Original inputs, reference
labels, model response and [frozen tool report](../report.json) remain unchanged.

The current-code [report](report.json) verifies the same complete pinned Next.js
archive and supplied context/path facts on Linux. Source commands, dependencies,
hooks and tests are never executed. Native discovery and research-only root
scope remain separate; the source path index is still larger than the AI packet.
The tool and development script have recorded source fingerprints. Package
version `0.23.0` alone does not identify this **unreleased** rule state; this is
not a scan with the immutable published v0.23.0 wheel.

| Scope | Files | Frozen findings | Development findings |
|---|---:|---:|---:|
| Native discovery | 27 | 8 `dead-path`, 1 `context-large` | 1 `context-large` |
| Research-only root | 1 | 8 `dead-path`, 1 `context-large` | 1 `context-large` |

The source was not improved between these runs; the checker removed its own
path false positives. The heuristic score changes from C 76 to A 94, but that is
**not an increase in instruction quality or a measured accuracy improvement**.
The independent reference remains unresolved, `comparison_ready` stays false,
correctness metrics remain null, and the earlier AI cleanup concern is not
adjudicated by these fixes. There is no new model or hybrid run.

## Offline reproduction

From a current source checkout, with `src` on `PYTHONPATH`, on a case-sensitive
filesystem compatible with the retained path facts:

```bash
python scripts/run_path_development_check.py \
  --archive /absolute/path/to/pinned-source.tar.gz \
  --output-dir /absolute/path/to/new-development-check
```

The archive must have SHA-256
`2d5323129612f58c16523d29e09032518207ee2743467c466e526fc5a26650b5`;
all tracked Git objects and supplied path facts are additionally checked. No
download is performed. A new output directory is required. A failed preparation
has no completed report and is not a clean prediction.

The helper applies the frozen source/scope/safety policy with **only the product
fingerprint replaced in memory** to verify current code. That explicitly derived
policy is not the frozen or preregistered tool. Its fingerprint and derivation
are retained separately. Never rewrite original protocols or present this
development case as untouched evaluation evidence. Future independent accuracy
work still needs new cases, matched scopes and independently adjudicated labels.
