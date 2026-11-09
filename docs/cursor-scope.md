# Cursor rule activation from declared file context

**Available in v0.25.0+, opt-in and unscored.** `scope` predicts which
root `.cursor/rules/` project rules attach automatically given explicitly
declared file paths. It does not query Cursor or observe an agent run.

```bash
agent-config-score scope . --target src/web/app.ts
agent-config-score scope . --target src/web/app.ts --target src/api/service.py --json
```

Repeat `--target` for every file assumed in context. Paths are normalized,
deduplicated, sorted and repository-relative. Windows separators are accepted;
absolute, drive-relative, parent-traversal and control-character paths are
rejected. Target existence and contents are not checked: the command can model
a proposed file that has not been created yet. Up to 64 inputs of 1,024
characters each are accepted.

## What the profile models

The `cursor-file-context-v1` profile follows the activation modes described in
the [Cursor rules documentation](https://cursor.com/docs/rules), checked on
2026-11-03. This is a bounded interpretation of that documentation, not a claim
of version-independent equivalence to Cursor's implementation.

| Recognized metadata | Model mode | Predicted activation |
|---|---|---|
| `alwaysApply: true` | `always` | Active for the declared context; valid scalar description/globs do not restrict it |
| `alwaysApply: false` and nonempty supported globs | `patterns` | Active if any declared file matches any pattern; otherwise inactive |
| `alwaysApply: false`, no globs, nonempty description | `agent_selected` | Unknown: file paths do not determine model selection |
| `alwaysApply: false`, no globs or description | `manual` | Unknown: manual mentions are not observed |
| Unsupported or ambiguous metadata | `unknown` | Unknown, including when no supported pattern matches |
| Plain `.md` under root `.cursor/rules/` | `ignored` | Inactive under the documented project-rule format |

“Active” means **predicted automatic attachment under this profile**. “Inactive”
means **not triggered by these paths**, not disabled or observed absent. Manual
references and runtime settings can change actual context. User/team rules,
other instruction formats, nested project roots, precedence, and the agent's
interpretation of attached text are not modelled. Directory names or proximity
to a rule do not add an inferred condition beyond its declared globs.

Globs trigger attachment when matching files enter context. They do not prove
an instruction can only affect those files. If a task includes both frontend
and backend files, both rule sets may attach even with disjoint globs. The
checker evaluates the complete declared file set instead of treating disjoint
patterns as a proof that contradictory text cannot co-activate.

## Bounded metadata and glob grammar

The first line may have a UTF-8 BOM and must be `---`. Closing `---` must occur
within the following 128 lines. Only unique, unindented `description`, `globs`
and `alwaysApply` keys, blank lines and comment lines are accepted. Boolean
flags must be unquoted lowercase `true` or `false`; missing flags stay unknown.

Description/globs accept empty values, plain strings with optional inline
comments, JSON double-quoted strings, or single-quoted strings with doubled
apostrophes. Full YAML is not implemented: lists, blocks, anchors, aliases,
duplicate/unknown keys, multiline values, implicit non-string scalars and
ambiguous syntax stay unknown. Quote numeric-looking intended strings and
glob strings starting with `*`. For `alwaysApply: true`, scalar syntax still
has to be recognized, but the glob language is not evaluated.

For conditional rules, globs are a comma-separated scalar with OR semantics,
at most 32 patterns of 256 characters each. Every pattern must be supported;
one unsupported pattern makes the rule unknown rather than falsely inactive.

| Pattern | Meaning in this profile |
|---|---|
| `*.ts` | A root-level filename ending in `.ts` |
| `**/*.ts` | A `.ts` file at any directory depth, including root |
| `src/**` | Files below `src`, including nested directories |
| `src/**/*.tsx` | `.tsx` files at any depth below `src` |
| `tailwind.config.*` | A matching root-level filename |
| `src/**, tests/**` | Either pattern |

Matching is case-sensitive, includes dot-prefixed components, and treats `/`
as a component boundary. `*` matches within one component; `**` is a whole
component matching zero or more directories. Terminal `**` requires a file
below the prefix, not a path equal to the prefix. Absolute paths, backslashes,
empty/dot/parent components, embedded `**`, `?`, braces, character classes,
negation and extglob syntax are unsupported. Different native matching behavior
or runtime settings may require a future profile revision.

The engine uses iterative component wildcard dynamic programming and a finite
set of segment states with zero-directory transitions for `**`. It does not
use recursive glob backtracking, enumerate the target filesystem, or attempt
to prove intersection/disjointness of arbitrary pattern languages.

## Opposing-directive review signals

For non-inactive rules with an interpretable body, the scanner reuses its
bounded English directive recognizer: for example, `Always use tabs` versus
`Never use tabs`. Recognized directive text is normalized before pairing.
Explicit examples, fences, quotes and comments are excluded using the existing
bounded prose context. Open example sections and HTML-like body markup leave
the body uninterpreted. This is not full Markdown, natural-language reasoning,
or an extraction of every constraint in a document.

Each pair retains both source paths, original one-based line numbers and
polarity, plus a SHA-256 of the normalized directive. Pair activation is active
only if both rules are predicted active; otherwise it is unknown. The report
includes the union of matched trigger paths and any shared target matches.
An empty shared set does not cancel multi-file co-activation. More than 10,000
pairs fails with exit `2` instead of emitting a partial clean-looking report.

These are textual review signals. Two identical opposing phrases could concern
different entities or contain qualifiers the grammar does not understand.
They are not proven semantic conflicts, exploitability, or a safety verdict.
No signals can mean no supported text, an inactive rule, or an uninterpreted
body; inspect the per-rule analysis and summary counts.

## Report, privacy and failure contract

JSON has `schema_version: 1`, `profile`, `status: "completed"`, `scored: false`,
the tool identity/source fingerprint, `targets`, `rules`, `opposing_directives`
and `summary`. `observed_agent_context` and `targets_existence_checked` are
always false. `activation_inputs` and `unmodelled_inputs` make the boundary
explicit. Each rule records mode, activation/reason, pattern count, metadata
line numbers, body start, matched targets, directive-analysis status and the
number of recognized directives considered for pairing. Inactive rules have
zero considered directives even when their body contains supported prose.
Read `.mdc` sources additionally carry a newline-normalized `source_sha256`;
unread formats have a null hash. This binds captured text without exporting it.

Reports retain source paths and supplied target paths. Raw descriptions, glob
values and directive bodies are not exported; hashes are not anonymization or
proof of authenticity. The command does not write reports, modify rules,
execute their instructions, upload files or contact maintainers.

Normal supported-source discovery and metadata/source preflight still run
across the repository, with existing ignores and skipped directories. An
unrelated unsafe/broken supported instruction link or ignore-file error can
therefore stop analysis. Only exact lowercase `.mdc` files under root
`.cursor/rules/` have their contents read here; other discovered instruction
formats are counted but not interpreted. Unknown extension casing remains
unknown. Existing containment checks and their non-atomic filesystem limits
apply; this is not an isolated selected-file traversal.

For standalone `scope PATH`, exit `0` means the advisory analysis completed, including signals and unknowns.
Invalid inputs, unreadable/invalid UTF-8 sources or resource-limit failures use
exit `2` without a successful JSON report. There is no exit `1` conflict gate,
score, policy threshold, suppression handling or pass/fail safety result.

Normal scan, compare, diff and Action scoring are unchanged. In particular,
the old general contradiction check is not suppressed by this new command.
The [comparison commands](cursor-scope-impact.md) additionally report bounded
before/after attachment and exact recognized-directive availability, with
explicit opt-in review gates. General effective-policy inheritance, semantic
constraint-impact analysis and execution-invariant verification remain outside
the implementation.
Try the [runnable synthetic example](../examples/cursor-scope/README.md).
