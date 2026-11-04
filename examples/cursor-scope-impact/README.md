# Cursor activation-change example

Requires an unreleased source installation after v0.24.0. These are synthetic
development fixtures, not real user cases or accuracy measurements. No agent or
instruction-file command is executed. Logical target files need not exist.

The same instruction, `Never delete files without approval`, appears in all
four trees. Only its attachment metadata or source filename changes. From the
repository root:

```bash
agent-config-score scope compare examples/cursor-scope-impact/base examples/cursor-scope-impact/narrowed --target src/api/service.py --fail-on-lost-directives --fail-on-unknown
```

Expected exit **1**: `src/**` becomes `src/web/**`. The declared API file stops
triggering the rule. One recognized baseline-active directive becomes inactive;
the report points to metadata line 2 and directive line 5. Ordinary standalone
scans of these two trees both score 100; that does not certify deletion safety.

```bash
agent-config-score scope compare examples/cursor-scope-impact/base examples/cursor-scope-impact/narrowed --target src/api/service.py --target src/web/app.ts --fail-on-lost-directives --fail-on-unknown
```

Expected exit **0**: the frontend file still triggers the rule in this multi-file
context. The report retains the lost API trigger match, but the exact directive
still has an active source. Trigger globs do not limit where an attached
instruction can have an effect.

```bash
agent-config-score scope compare examples/cursor-scope-impact/base examples/cursor-scope-impact/renamed --target src/api/service.py --fail-on-lost-directives --fail-on-unknown
```

Expected exit **0**: the old rule file is removed and a new one is added, but the
same normalized directive/polarity remains in an automatically attached rule.
File lifecycle changes stay visible without becoming a lost-directive failure.

```bash
agent-config-score scope compare examples/cursor-scope-impact/base examples/cursor-scope-impact/uncertain --target src/api/service.py --fail-on-lost-directives --fail-on-unknown --json
```

Expected exit **1** for **unknown**, not a definite inactive directive. Removing
globs with `alwaysApply: false` makes loading depend on manual mentions, which
this profile does not observe. `--fail-on-unknown` requests review of that
uncertainty; `--fail-on-lost-directives` alone does not block it.

For a real local Git change, use:

```bash
agent-config-score scope diff origin/main --target src/api/service.py --fail-on-lost-directives --fail-on-unknown --json
```

The candidate is the working tree, including uncommitted changes. The report
retains the resolved baseline commit. Default comparisons are advisory; the two
flags explicitly opt into a review gate. See the [comparison contract and CI
example](../../docs/cursor-scope-impact.md) for exact-recognition, unknown,
privacy and operational-error limits.
