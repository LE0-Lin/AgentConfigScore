# AgentConfigScore Benchmark v1

Deterministic contract cases: **122/122 exact matches**.

- Precision: **100.0%**
- Recall: **100.0%**
- F1: **100.0%**
- Clean negative controls: **50/50 passed**

| Category | Exact matches | Accuracy |
|---|---:|---:|
| `clean` | 7/7 | 100.0% |
| `contradiction` | 6/6 | 100.0% |
| `coordination` | 1/1 | 100.0% |
| `coverage` | 7/7 | 100.0% |
| `danger` | 42/42 | 100.0% |
| `negation` | 36/36 | 100.0% |
| `path` | 12/12 | 100.0% |
| `regression` | 5/5 | 100.0% |
| `secret` | 6/6 | 100.0% |

## Open challenge set

Detected **4/8** labeled challenges. Challenge results are reported but do not control the benchmark exit code.

| Challenge | Category | Detected | Observed rules |
|---|---|---:|---|
| `harmful-prose` | `semantic` | no | — |
| `paraphrased-contradiction` | `semantic` | no | — |
| `powershell-download-execute` | `danger-surface` | yes | `powershell-download-exec` |
| `git-clean-force` | `danger-surface` | yes | `git-clean-force` |
| `docker-system-prune` | `danger-surface` | yes | `docker-system-prune` |
| `kubectl-delete-namespace` | `danger-surface` | yes | `kubectl-delete-namespace` |
| `replace-good-with-bad-prose` | `semantic` | no | — |
| `secret-exfiltration-intent` | `semantic` | no | — |

The contract tier measures behavior the deterministic scanner currently promises. The challenge tier keeps known semantic and rule-surface misses visible instead of inflating the headline metric.
