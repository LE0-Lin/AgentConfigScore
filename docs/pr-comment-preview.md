# Optional PR comment preview

This synthetic rendering is produced by the actual workflow script against a fake GitHub client. No comment was posted and the example run URL is a placeholder. The numeric outcomes illustrate a missing link plus an explicit prior-instruction override; this is not user feedback or a real CI incident.

---

<!-- agent-config-score:regression -->
### AgentConfigScore

**Blocked** · Score: 100 → 88 (-12)

| New findings | New errors | Resolved |
|---:|---:|---:|
| 2 | 0 | 0 |

#### New findings by rule

| Severity | Rule | Count |
|---|---|---:|
| warning | `dead-path` | 1 |
| warning | `prompt-injection-override` | 1 |

[View findings and policy result](https://github.com/owner/repo/actions/runs/123)

Review the source locations and suggested next steps in the full report.
Reproduce locally with `agent-config-score diff --explain` using the same baseline; inspect a rule with `agent-config-score rules RULE_ID`.

The score covers detected rule matches; review individual findings.
