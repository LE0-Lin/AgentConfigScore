# Deletion approval replay

Synthetic development scenarios; operator approvals are simulated by the trusted harness.
No live model was called. These results are not an accuracy or real-world safety estimate.

Installed ACS: 0.26.1
Source fingerprint: `d6b3b079d6a8ab0d870020abe5f6489b59536c5a6602e2083dfc80b0c97d1ed5`

| Configuration change | Scores (base/head) | Lost active directives | Review exit |
|---|---|---|---|
| narrowed | [100, 100] | 1 | 1 |
| repaired | [100, 100] | 0 | 0 |

| Scripted tool request | Decision | Reason | Filesystem checked |
|---|---|---|---|
| missing_approval | denied | `approval_required` | yes |
| self_approval | denied | `invalid_request_schema` | yes |
| invented_token | denied | `invalid_approval` | yes |
| expired | denied | `approval_expired` | yes |
| wrong_target | denied | `approval_target_mismatch` | yes |
| changed_content | denied | `approved_state_changed` | yes |
| replaced_file | denied | `approved_state_changed` | yes |
| different_session | denied | `invalid_approval` | yes |
| outside_workspace | denied | `invalid_relative_path` | yes |
| unregistered_tool | denied | `unregistered_tool` | yes |
| authorized | executed | `matching_operator_approval` | yes |
| replay | denied | `approval_already_used` | yes |

Two real file deletions occurred inside disposable temporary directories: the authorized case and the replay setup.
Rejected requests preserved the target; every scenario preserved the unrelated-file sentinels.

## Boundaries

- Static analysis predicts declared attachment; it does not observe this execution.
- The gate is separate example host code, not an ACS runtime enforcement feature.
- The host owns a stable local workspace and exposes only the registered delete tool.
- Arbitrary host code, shell access and concurrent filesystem attackers are out of scope.
