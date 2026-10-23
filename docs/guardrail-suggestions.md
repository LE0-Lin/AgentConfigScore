# Opt-in deletion safeguard review and completion

This is an **unreleased source feature** after v0.23.0. Existing PyPI packages,
release tags and rolling Action refs have not been replaced.

`guardrails` asks a different question from lint scoring: **does this selected
file contain a narrowly recognized deletion-related constraint, and would a
reviewed addition help?** No recognized wording means `review_needed`, not proof
of danger, absence of all safeguards, or a score penalty. A recognized sentence
is not evidence that an agent actually obeys it.

## Preview first

```bash
agent-config-score guardrails . --file AGENTS.md
agent-config-score guardrails . --file CLAUDE.md --json
agent-config-score guardrails . --file AGENTS.md --template-language simplified
```

The default target is the existing root `AGENTS.md`. Choose another existing,
supported, non-ignored instruction file explicitly with `--file`; the command
does not create missing instruction files or silently choose another agent's
configuration. Paths must be repository-relative and cannot escape the root.
The target must be a regular in-repository UTF-8 file of at most 1 MiB.

The preview reads but does not modify files or save a plan. It reports evidence
line numbers/kinds without quoting old instruction text, and otherwise proposes
a block requiring explicit user approval before deleting existing files,
overwriting user changes or discarding uncommitted work. The block preserves any
stricter existing rules; it does not authorize destructive commands.

`--template-language` accepts `en`, `simplified` and `traditional`. It changes only
the proposed block, not CLI messages, rule IDs or general language support.

## Confirm the specific proposal

Read the **entire target file**, relevant ancestors, tool configuration and the
proposed addition. Resolve conflicting policies before proceeding. Then rerun
the **same preview command** with `--apply TOKEN`, replacing `TOKEN` with the
64-character confirmation printed by that preview. Preserve its `--file` and
`--template-language` choices. There is no blind `--apply`/`--force` shortcut.

The confirmation binds canonical repository location, relative filename, file
identity/size/modification time, exact original bytes and the actual proposed
append bytes. A changed file, another destination or a different template needs
a fresh preview for any new append. A token is not a signature, secret authorization credential or
proof of human review: automation can echo it without reading anything.
Other files, inherited policies and external settings are not bound into the
token. Review that context again if it changes.

The confirmed operation appends only; it does not replace or truncate the file.
Original bytes, UTF-8 BOM and existing permissions remain; LF/CRLF additions follow
the selected newline convention (mixed/lone-CR files use LF). Repeating the
operation on a now-recognized constraint is a no-op, even with the old token.
Review the diff and rerun normal lint/regression checks afterward. Adding text
can affect independent token/duplication checks; there is no completion bonus.

Internal file aliases, hard-linked/unknown-link-count targets and unknown file
identities are preview-only.
Sources with HTML/comment markup, an unclosed fence or detected unclosed
frontmatter also require manual merging. This intentionally conservative layout
guard is not a complete Markdown parser. Closed MDC frontmatter is preserved.

Opening and appending recheck source boundaries, regular-file identity, link
count and exact contents; no-follow/nonblocking flags are used where available.
This is **not an atomic filesystem transaction or hostile-filesystem sandbox**.
Uncooperative concurrent writers or parent/target replacement can still race
checks. Keep the repository stable. A failed/partial write returns exit `2`
without success JSON but may leave a partial appended fragment: inspect the file
before retrying. It never attempts a destructive rollback of concurrent edits.

## Recognition and coverage limits

First-version examples include `Never use rm -rf`, `Do not delete files without
explicit user approval`, `Always ask for confirmation before deleting files`,
and narrow Chinese forms such as `删除前必须征得确认`. All three canonical addition
templates are recognized. A ban on `rm`/`rmdir` is labeled `specific_command_ban`,
not a general approval-before-deletion policy. These finite patterns do not
understand arbitrary paraphrases, command aliases/options or other languages.

Fenced/indented code, blockquotes, full-line quotes, headings, detected comments
and leading YAML frontmatter do not count as recognized active policy. Long or
ambiguous sentences, exceptions, optional suggestions and reversed statements
remain unrecognized. This is a heuristic, not a Markdown AST or intent classifier.

Only the **selected file** is reviewed. Ancestor instructions, other files,
agent-specific precedence/globs and external permission/sandbox settings are not
inherited or assessed. A review-needed result may therefore be unnecessary in
context; a recognized result may still coexist with unsafe or conflicting
instructions. Do not blindly append generic policies to every file.

## Output, privacy and compatibility

`--json` uses `schema_version: 1`, check ID `deletion-safeguards`, scope
`selected_file_only`, evidence, proposed text, confirmation, manual-review reasons,
captured tool identity and an `applied` flag. Statuses are `recognized`,
`review_needed` or `appended`. None is a score or security certification.
Exit `0` means review/append completed, not that the repository is safe; invalid
inputs, stale confirmation and expected operational failures use exit `2`.

Nothing is uploaded. Raw old text is not exported, but filenames, evidence
locations and the content-bound confirmation can reveal or link private context;
do not treat this output as the privacy-minimized `feedback` report. Inspect it
before sharing. No API, runtime dependency, new scored rule, suppression ID,
score policy or default scan/CI behavior is added. Appending a block does not
neutralize an already present dangerous instruction; normal lint still detects it.
The maintained synthetic tests are not independent accuracy or user-value evidence.
