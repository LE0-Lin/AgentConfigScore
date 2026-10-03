# Benchmarks

AgentConfigScore keeps two deliberately different forms of evidence:

- an offline adversarial mutation suite for reproducible rule behavior;
- a pinned public-repository smoke suite for checking scanner noise on real inputs.

Neither benchmark is a claim that A 100 means semantic prompt quality.

## Adversarial mutation Benchmark v1

Benchmark v1 contains 328 deterministic contract cases and 8 explicitly labeled
open challenges. The contracts cover positive detections and clean negative
controls across `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, legacy and modern Cursor
rules, and GitHub Copilot instructions.

The current committed result is:

- 328/328 exact contract matches;
- 189 expected rule detections with no extra or missing rule IDs;
- 140/140 clean negative controls;
- 4/8 challenge cases detected after adding four narrow danger-surface rules.

The 100% contract precision and recall describe this closed, maintained test
suite only. They are not estimates of real-world precision or recall. The 4/8
challenge result—and the four remaining semantic misses—is published beside
them to make that boundary impossible to miss.

Run the fully offline benchmark:

```bash
python scripts/run_adversarial_benchmark.py \
  --output benchmark-result.json \
  --markdown benchmark-report.md
```

See the [labeled corpus](adversarial_cases.json) and [committed report](adversarial-v1-report.md).
Tests regenerate the report and require it to remain synchronized with scanner
behavior.

The instruction-context cases pair explicit prohibited blocks with active,
unclosed, conditional, and out-of-scope controls. Markdown-context cases test
matching fence markers and lengths. Literal synthetic credentials remain
detectable inside negative examples, and regression cases remove a prohibition
label or closing fence to verify that a candidate cannot keep its exemption.

## Real-repository smoke benchmark

This benchmark scans pinned commits from six public projects with coding-agent
instructions. It is
designed to make scanner behavior reproducible and to catch noisy path heuristics
before release. It is not a ranking of the projects or a claim that six
repositories represent every instruction style.

For the exact meaning of A 100 and adversarial cases the deterministic scanner
cannot judge, read the [score contract and known limitations](../docs/limitations.md).

| Repository | Commit | Instruction files | Score | Reviewed findings |
|---|---|---:|---:|---|
| `openai/codex` | `d58d0e5` | 2 | B 82 | 3 absent `.rs` path occurrences; 1 context-size warning |
| `anomalyco/opencode` | `9f69463` | 18 | A 94 | 1 context-size warning |
| `browser-use/browser-use` | `d379a32` | 2 | B 88 | 1 context-size warning |
| `Reaparr/Reaparr` | `d9926d6` | 1 | A 100 | Prohibited `rm -rf` replacement-table example remains clean |
| `olup/origan` | `95ac789` | 1 | B 88 | 1 active aggressive Docker cleanup error |
| `restsharp/RestSharp` | `64ee129` | 3 | B 84 | Lowercase `agents.md`; 1 context warning and 1 active broad recursive-deletion error |

All nine findings in the recorded run were manually checked against their rule
definitions. In particular, the reviewed output contains no `dead-path` finding
for API symbols, package imports, documentation URLs, code-fence examples,
platform paths, or generic filename conventions.

Run it from an AgentConfigScore checkout:

```bash
python -m pip install -e .
python scripts/run_real_world_benchmark.py --output benchmark-result.json
```

Reproduce one reviewed case without downloading the entire corpus:

```bash
python scripts/run_real_world_benchmark.py \
  --repository restsharp/RestSharp
```

The script clones but never executes code from the target repositories. It
checks out the exact commits in `corpus.json`, scans them, compares stable
finding fingerprints with the reviewed expectations, and exits non-zero on a
mismatch. Use `--work-dir DIR` to retain the clones for inspection.
Only one pinned commit is fetched for each repository. Stalled Git commands
time out after 180 seconds with the failed command identified in the error.

The corpus is intentionally small and transparent. Contributions that add a
pinned repository should include a short manual-review note and must not treat
the resulting score as a quality leaderboard.
