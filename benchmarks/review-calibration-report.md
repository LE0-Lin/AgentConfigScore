# Instruction review comparison

Dataset tier: **calibration**. Labels: **provisional**.

Calibration results are development evidence, not an independent accuracy estimate.

Scored cases: 11; unresolved labels excluded: 1.

| Reviewer | Status | Coverage | False positives | Misses | Unreviewed | Precision | Recall | F1 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| AgentConfigScore | complete | 100.0% | 0 | 2 | 0 | 100.0% | 71.4% | 83.3% |
| AI / hybrid | not run | n/a | n/a | n/a | n/a | n/a | n/a | n/a |

Incomplete reviews do not receive headline precision, recall, or F1; missing answers never count as clean.
Hybrid is a three-valued OR, not an AI adjudication of tool findings. Unknown API cost and latency remain null in JSON.

## Tool disagreements with reference labels

- paraphrased-test-conflict: miss (semantic).
- environment-exfiltration: miss (semantic).
