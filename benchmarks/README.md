# Real-repository smoke benchmark

This benchmark scans pinned commits from three public AI coding projects. It is
designed to make scanner behavior reproducible and to catch noisy path heuristics
before release. It is not a ranking of the projects or a claim that three
repositories represent every instruction style.

For the exact meaning of A 100 and adversarial cases the deterministic scanner
cannot judge, read the [score contract and known limitations](../docs/limitations.md).

| Repository | Commit | Instruction files | Score | Reviewed findings |
|---|---|---:|---:|---|
| `openai/codex` | `d58d0e5` | 2 | B 82 | 3 absent `.rs` path occurrences; 1 context-size warning |
| `anomalyco/opencode` | `9f69463` | 18 | A 94 | 1 context-size warning |
| `browser-use/browser-use` | `d379a32` | 2 | B 88 | 1 context-size warning |

All six findings in the recorded run were manually checked against their rule
definitions. In particular, the reviewed output contains no `dead-path` finding
for API symbols, package imports, documentation URLs, code-fence examples,
platform paths, or generic filename conventions.

Run it from an AgentConfigScore checkout:

```bash
python -m pip install -e .
python scripts/run_real_world_benchmark.py --output benchmark-result.json
```

The script clones but never executes code from the target repositories. It
checks out the exact commits in `corpus.json`, scans them, compares stable
finding fingerprints with the reviewed expectations, and exits non-zero on a
mismatch. Use `--work-dir DIR` to retain the clones for inspection.

The corpus is intentionally small and transparent. Contributions that add a
pinned repository should include a short manual-review note and must not treat
the resulting score as a quality leaderboard.
