# Cursor file-context example

Requires an unreleased source installation; the published v0.24.0 package does
not include `scope`. These are synthetic, deliberately opposing formatting
instructions, not real user evidence or a recommended instruction template.

From the repository root:

```bash
agent-config-score scope examples/cursor-scope --target src/web/app.ts
agent-config-score scope examples/cursor-scope --target src/web/app.ts --target src/api/service.py --json
```

The targets are logical repository-relative file paths assumed to be in the
agent's context. They do not need to exist; their contents are never opened.

The first command predicts frontend **active**, backend **inactive** (not
triggered by the declared path), and review **unknown** (model selection cannot
be inferred from file paths). It produces no opposing-directive signal.

The second predicts both formatting rules active and reports one opposing pair
at `frontend.mdc:5` and `backend.mdc:5`. Their patterns share no target here, but
both rules can attach in a multi-file task. Disjoint globs are not evidence
that the instructions cannot co-activate. `review.mdc` remains unknown.

Both commands return `0` for completed advisory analysis, even with signals or
unknowns. Input/read errors return `2`. There is no score or blocking CI gate.
The normal scan still reports its original cross-file contradiction; this
separate profile does not suppress findings or change existing score semantics.

See the [model, metadata grammar and limitations](../../docs/cursor-scope.md).
