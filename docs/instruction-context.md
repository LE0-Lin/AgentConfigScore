# Instruction context and scope

Danger detection needs more than finding a command-shaped string. The same
command can be an execution instruction or an explicitly prohibited example.
AgentConfigScore uses a small, deterministic document-context layer to distinguish
a narrow set of these cases while preserving source offsets and finding lines.
It does not claim to understand arbitrary natural language.

## Explicit prohibited blocks

This is a prohibited example, so it does not produce an `rm-rf` finding:

````markdown
Never run these commands:

```sh
rm -rf outputs
```
````

The introductory line must match the supported prohibition grammar, and the
fence must close. At most one blank line may separate the label from the block.
The exemption ends at the matching closing fence:

````markdown
Never run these commands:
```sh
rm -rf outputs
```
Run rm -rf outputs.
````

The last line still produces an `rm-rf` finding. Removing the introductory label
or closing fence exposes the dangerous command to the normal scan and regression
gate. Merely writing `Examples:` above a code fence does not exempt it.

## Direct command lists

Contiguous direct command entries can inherit the same narrowly labeled
prohibition:

```markdown
Do not execute the following commands:
- rm -rf outputs
- git clean -fdx
```

Blank lines, a change of indentation or list-marker family, headings, and ordinary
paragraphs end this scope. An entry beginning with prose such as
`Instead run rm -rf outputs` does not inherit the exemption. Ordered lists must
keep the same delimiter (`1.` / `2.` or `1)` / `2)`); numbers may change.

## Supported labels

Labels are whole lines ending in a colon, not a keyword anywhere in a paragraph.
Matching is case-insensitive and tolerates inline Markdown emphasis. The grammar
recognizes these forms:

- `Never run these commands:`
- `Do not execute the following commands:`
- `Don't use any of the following commands:`
- `Must not use these commands under any circumstances:`
- `The following commands are prohibited:`
- `The following instructions are forbidden:`
- `Do not follow these instructions:`

In the first four forms, `run`, `execute`, `use`, and `follow` may be exchanged;
`commands` and `instructions` may be exchanged. Explicit instruction labels can
therefore cover an override phrase such as `ignore previous instructions` inside
a closed block. Heading-only labels, code-quoted labels, and labels inside block
quotes are not inherited. More elaborate prose needs review and, if appropriate, an auditable
suppression rather than a guessed exemption.

## Safety boundaries

| Input | Treatment |
|---|---|
| Unlabeled fenced dangerous command | Reported normally |
| Clearly prohibited, adjacent, closed command block | Danger finding excluded within that scope |
| Unclosed or incorrectly closed prohibition fence | No inherited danger exemption |
| Conditional label or exception word (`but`, `however`, `except`, `unless`) in the block | No inherited danger exemption |
| An explicit affirmative prefix (`always`, `must`, `run`, `execute`, `use`, `follow`) before a command inside the block | Command remains reviewable |
| Literal credential-shaped material in any example | Secret rule remains active |
| Active command after the prohibited block/list | Reported normally |

The existing nearby replacement-table exception also stops at headings, thematic
breaks, and code fences. A command table in a new section is not exempted by a
prohibition in the previous section.

## Implementation and deliberate limits

The scanner builds the line contexts once per instruction file. Each line retains
source offsets, its block kind, and any recognized prohibition scope. Danger
candidates are then interpreted with the command grammar and this context; local
path checks reuse the same fence boundaries. No instruction or command is executed.
Literal credentials bypass danger-context exemptions. The public report schema
is unchanged, and existing stable rule IDs are retained.

The supported fence subset follows the marker and length rules in the
[CommonMark fenced-code specification](https://spec.commonmark.org/0.31.2/#fenced-code-blocks):
backtick and tilde markers are distinct, a closing fence must be at least as long
as its opener, and a closing fence cannot have trailing info text. Opening
backtick info strings cannot contain backticks. Fences indented by zero to three
spaces are supported. Block-quote containers, deeply nested list containers,
indented code blocks, front matter, and a complete Markdown AST are not modeled.

The context layer is shared by dangerous-command and path checks, not yet by all rules.
It also supplies prose/list eligibility for [misleading verification reporting](verification-reporting.md)
and [bulk environment-upload warnings](environment-upload.md). Those narrow
**prose** rules decline code/quoted examples, unlike dangerous-command rules;
that is not a blanket exemption for dangerous commands or literal credentials.
Contradiction detection still uses conservative exact directive-body matching
and file precedence; duplication and token budgeting still consider raw text.
Context alone does not solve arbitrary semantic challenges or turn an A 100
score into an instruction-quality guarantee.

See the [score contract and limitations](limitations.md) and the
[offline adversarial benchmark](../benchmarks/adversarial-v1-report.md).
