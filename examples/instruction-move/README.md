# An instruction moves to a new scope

A merged public PR moved `docs/AGENTS.md` to the repository root with an identical Git blob. Replaying its full before and after trees with v0.24.0 produced 100 on both sides. With new errors gated, the comparison reported `instruction-file-removed` for the former path and exited 1. The PR described the move as intentional so agents could discover the file at the root. The finding identifies the original path to review when approving the migration.

This reduced example uses original sample wording and adds a repository policy so the result can be reproduced offline from a checkout. Its input captures the same path change and preserves identical instruction bytes. Project and contributor identities are omitted.

## Reproduce

From the AgentConfigScore checkout, install the published version in a virtual environment and run:

```bash
python -m pip install agent-config-score==0.24.0
cd tests/fixtures/contracts/regression/instruction-move
agent-config-score compare base head
agent-config-score compare base base
agent-config-score compare head head
```

| Comparison | Baseline → candidate | New rule | Exit |
| --- | --- | --- | --- |
| Original scope → root | 100 → 100 | `instruction-file-removed` at `docs/AGENTS.md` | 1 |
| Original scope → itself | 100 → 100 | None | 0 |
| Root → itself | 100 → 100 | None | 0 |

The first exit is expected. Run the comparisons separately if your shell stops on an error. Add `--json` to inspect the scores, stable rule ID, and former file path.

The same-directory rename heuristic deliberately requires a matching directory. This cross-directory move merits review even with byte-identical text. The decision to accept the migration depends on the client's loading rules and the intended scope.
