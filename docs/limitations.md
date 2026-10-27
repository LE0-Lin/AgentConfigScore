# What the score does—and does not—mean

English | [简体中文](simplified/limitations.md) | [繁體中文](traditional/limitations.md)

AgentConfigScore is a deterministic linter and regression gate for persistent
coding-agent instructions. Its score measures detected, rule-defined risks. It
does not measure whether an AI agent is intelligent, whether a prompt will solve
a task, or whether an instruction file is generally “good.”

**An A 100 result means that no active deterministic rule matched. It is not a
semantic quality certification.**

v0.24.0+ includes [tool source identity](report-identity.md) to
distinguish implementations that declare the same version. A matching digest is
not an accuracy result or a reproducibility guarantee: repository inputs, policy,
runtime and filesystem behavior are outside that fingerprint. Missing source is
explicitly unknown, and historic reports are not relabelled.

## Configuration decoding

Unreleased source builds reject duplicate decoded JSON member names at every
configuration depth, non-standard `NaN`/`Infinity` constants and a Boolean format
`version`. They do not choose the first or last repeated value. Both comparison
trees must validate; CLI threshold overrides cannot authorize malformed config.
`doctor` uses one read for policy and schema metadata. These changes are not in
v0.24.0. See [failure and compatibility details](doctor.md#configuration-decoding).
The check does not validate policy adequacy, authenticate config authors, provide
an atomic snapshot or recover names already lost by a caller's JSON decoder.

## Local history integrity

Unreleased source builds distinguish an absent local history index from damaged
or unreadable data. Invalid history returns operational exit `2`, not an empty
success report. The Python append helper refuses to reset it and uses a complete
same-directory replacement instead of truncating existing bytes. Partial legacy
snapshots remain supported; missing scores are unknown. Linked/reparse history
paths require manual migration. These changes are not in v0.24.0.

History validation is not evidence authenticity, policy/tool comparability or
semantic quality. The append helper needs serialized writers and does not claim
locking, a hostile-filesystem transaction or power-loss durability. Normal scans
do not automatically record local snapshots; immutable CI artifacts are separate.
See [recovery, retention and metadata limits](score-history-cli.md).

## Instruction-file filesystem boundary

Selected instruction files and `.agentconfigscoreignore` must resolve to regular
files inside the resolved scan root. Internal file symlinks remain supported;
findings, Markdown links and instruction scopes use the discovered alias's
repository-relative location, not the shared target's directory. An explicitly
supplied root alias is allowed and defines the resolved boundary.

Discovery does not descend through child directory symlinks or Windows junctions,
even when their targets are internal. Excluded dependency/build trees and
subtrees covered by an ignore pattern ending in `/**` are pruned before descent.
Other ignore patterns retain their filename-matching meaning. A source explicitly
excluded from discovery is not inspected and has no coverage claim.

Selected external, dangling, cyclic or non-regular file sources fail before their
contents are opened. Sources are revalidated before reading, and the resolved
target is opened. Failed discovery, resolution or instruction-content reads are
operational errors: scan/compare/feedback return `2` without a successful score or
new success report. `doctor` checks source readability and reports an `instructions`
error with exit `1`. Raw target paths and filesystem error details are not echoed
in these source diagnostics. Legacy `read-error` remains in the catalog for old
report/suppression compatibility, but cannot suppress a current operational failure.

This is **not a filesystem sandbox or an atomic snapshot**. A concurrent process
can still replace parents or targets between validation and open. Hard-link
identity and mount boundaries are not certified. Other explicitly chosen inputs,
configuration/workflow readers and report destinations are separate interfaces;
this guard does not claim to constrain every filesystem operation in the tool.
Non-instruction link cycles are excluded from the path index, not judged safe or
semantically correct. Keep repositories stable while scanning.

## Command interpretation

The `rm-rf`, `git-clean-force`, and `docker-system-prune` rules tokenize bounded
shell fragments before interpreting options. They recognize reordered, split,
and long options, explicit line continuations, and quoted option values. Shell
separators and `--` stop option interpretation. Git preview/interactive modes
are excluded; for `rm`, a later interactive option overrides force. An option
used as an exclusion/filter value is not treated as an execution flag.

This is a conservative command grammar: options after ordinary operands,
shell variable expansion, aliases, wrapper functions, and global options before
subcommands are not resolved. Fragments are limited to 1,000 characters. Only
explicit backslash continuations span lines. Other command rules still use
narrow patterns. English prohibitions are scoped conservatively; arbitrary
prose and other languages need human review.

The scanner also builds a shared, source-positioned document context once per
file. A narrowly recognized English prohibition can cover an immediately adjacent
closed fence or a contiguous list of direct command entries. This is not a full
Markdown parser or an intent classifier: unlabeled code remains active for
dangerous-command rules, unclosed fences do not inherit prohibitions, and literal
credentials are checked independently. See the supported grammar and safety
boundaries in [instruction context](instruction-context.md).

Option behavior is checked against the [Git clean manual](https://git-scm.com/docs/git-clean),
[GNU rm manual](https://www.gnu.org/software/coreutils/manual/html_node/rm-invocation.html),
and [Docker prune reference](https://docs.docker.com/reference/cli/docker/system/prune/).

## Prompt-injection warnings

The `prompt-injection-override` warning recognizes explicit English phrases such
as `ignore previous instructions`. A match is a review signal, not proof of an
attack. Explicit prohibitions and whole-line examples such as
`Attack example: "ignore previous instructions"` are excluded. Quotes or code
fences alone do not exempt a phrase. An explicit adjacent prohibition such as
`Do not follow these instructions:` can also cover a closed instruction block.
More elaborate educational examples can
still trigger warnings; use a reasoned suppression after review. This rule does
not detect arbitrary paraphrases, other languages, or instructions delivered at
runtime through tool output or remote content.

## Verification reporting

The `false-success-report` error requires a complete English prose clause that
explicitly conceals errors while reporting success, or claims tests passed
despite failure or without running them. Merely skipping tests, prohibitions,
and quoted/code examples are not enough. It does not combine evidence across
sentences or lines, inspect actual test execution, or judge arbitrary workflow
intent. Other harmful prose can still pass. See the [supported grammar and
negative controls](verification-reporting.md).

## Bulk environment transfers

The `broad-environment-upload` warning requires an explicit transfer action,
a full environment-variable source, and a network sink in one English prose
clause. Names-only metadata, qualified redaction, logs, prohibitions, and code
examples do not satisfy this grammar. The scanner does not examine the process
environment, verify sanitization, resolve destinations, or prove malicious
intent. Literal loopback is excluded without analyzing forwarding. Shell uploads,
other languages, and arbitrary paraphrases remain unsupported. See the
[supported evidence and deliberate limits](environment-upload.md).

## Local Markdown links

Simple inline links and image destinations are checked relative to the instruction
file's directory. For example, `[Guide](../CONTRIBUTING.md#setup)` checks that the
file exists inside the repository; it does not validate the `setup` heading.
URL-encoded spaces and angle-bracket destinations are supported. Remote links,
anchor-only links, fenced examples, absolute paths, and paths escaping the
repository are skipped. Nested parentheses in inline link destinations are not
currently parsed. This is a limited link check, not a full Markdown validator.

Unreleased source builds additionally check simple full `[Guide][setup]` and
collapsed `[setup][]` reference links, including images, when a matching
single-line definition such as `[setup]: GUIDE.md` exists in the same instruction
file. Paths stay document-relative; a missing used target is reported once at
its definition line. Labels use Unicode case folding and ASCII whitespace
normalization; the first matching definition wins, including external/anchor
targets. This follows the relevant [CommonMark reference-link conventions](https://spec.commonmark.org/0.31.2/#reference-link),
not full parser conformance. Unused supported definitions and resolved captions
are not separately treated as prose paths. These changes are not in v0.24.0.

This subset accepts at most 999 label characters without escapes/nested brackets,
zero to three spaces before top-level definitions, bare/angle destinations and
optional single-line quoted/parenthesized titles. Definitions must start a block
or follow another supported definition; they cannot interrupt a paragraph.
Fenced/indented code, escaped links and matched inline code do not activate new
reference checks. Shortcut `[setup]`, multiline definitions/labels, container
definitions, escaped or parenthesized destinations and HTML-like layouts need
manual review. Unknown first definitions do not select later duplicates. Inline
code recognition is conservative, not a complete block parser; unsupported forms
may remain unchecked. Existing inline/prose checks and independent danger rules
still run; reference handling does not exempt commands or certify file contents.

## Plain prose path references

Backtick file references starting with `./` or `../` are checked against the
repository root and applicable instruction-directory bases. Nested AGENTS-family
files retain their in-repository ancestor interpretations; other formats also
accept an explicit document-relative reference. These paths cannot pass merely
because an unrelated package has a matching suffix. Significant leading dots,
such as `.github`, are preserved. If no interpretation stays inside the repository,
the reference is skipped rather than probed outside or substituted with an
indexed path. Actual Markdown links remain strictly document-relative.

Unprefixed prose still uses conservative package-relative suffix matching.
Neither mode infers the working directory of a described command, follows `cd`
instructions, or proves which interpretation the author intended.

File-like prose references are heuristic, not a complete natural-language path
resolver. An immediate, closed `(if exists)` or `(if it exists)` condition makes
only that prose reference optional; Markdown link destinations remain checked.
An explanatory suffix after `-` or `:` inside that condition is supported.
Unclosed conditions, distant optionality words and unrelated paths on the same
line do not receive this exemption.

Two-component slugs such as `owner/tool.js` are excluded only in narrow,
same-line repository roles: followed by `repository`/`remote` and punctuation,
or after `merge target is`, `fork of`, `re-pushed to a branch in`, or
`CI trusts branches inside`. A repeated same-slug `fork of ... and not ... itself`
form is also recognized. Merely mentioning GitHub or a repository does not
exempt local paths. Other paraphrases and languages may still be misclassified.

Package-relative suffix lookup includes existing paths under `build`, `dist`,
`target` and `.next`; instruction discovery still skips those trees. Dependency
and administration trees remain excluded from the suffix index, directory
symlinks are not traversed, and external/broken symlink entries are excluded.
Existence does not establish that a file is authoritative, generated correctly,
or intended by an ambiguous reference. Generated/untracked files not present in
the checkout can still be reported missing; filesystem case behavior remains
host-dependent. These exemptions do not disable command or credential checks.

Directory traversal errors while building the index stop the scan with an
operational error, not a partial clean report or inferred missing path. CLI scan,
compare and feedback return exit `2` without a success report; `doctor` exposes
an error check named `repository-paths` and returns `1`. Dependency/admin trees
excluded from the index remain pruned. This is a local filesystem check, not a
Git-tracked-only index or an atomic filesystem snapshot.

## Red-team audit

The project added the following adversarial cases after testing the v0.18.0
scanner against empty, misleading, and deliberately weakened instructions.

| Case | v0.18.0 behavior | Hardened behavior |
|---|---|---|
| Repository has no supported instruction file | A 100 | `no-config` error; below A |
| Supported instruction file is empty | A 100 | `empty-instructions` error; below A |
| An active error has a small numeric penalty | Could still display A | Active errors cap the result below A |
| `Must X` and `Must not X` appear together | Missed | `contradiction` error |
| A prohibition-like double negative precedes a dangerous command | Dangerous command could be hidden | Dangerous command remains active |
| Candidate deletes an instruction file | Could report no regression | `instruction-file-removed` error |
| Candidate changes `Always X` to `Never X` | Could report no regression | `directive-polarity-flip` error |

Each hardened case has an automated regression test. In v0.24.0+,
only one-to-one, nonempty exact decoded-text moves to newly added supported files
in the same directory are exempt from removal. Existing copies, cross-directory
moves and whitespace-folded lookalikes are not exemptions. This does not certify
equivalent agent/format/scope behavior. Baseline-owned suppressions can document
an intentional exception. See [regression coverage](regression-coverage.md).

v0.24.0+ comparisons also reuse each scan's captured instruction text rather
than reopening sources and silently skipping second-read failures. Initial read
failures still stop the check; raw captured text is not retained in public report
objects or exports. This is not an atomic snapshot or concurrent-change detector.
Regression-only errors can coexist with two standalone `100` scores; enable the
baseline's `fail_on_new_errors` policy or `--fail-on-new-errors` to block them.
The bare CLI's score-only compatibility default is unchanged.

## Known blind spots

v0.24.0+ `--explain` output and the [maintainer checklist](best-practices.md)
give static review guidance, not new detection coverage or an automatic fix.
They do not execute referenced commands, infer replacement paths, change score
arithmetic or certify safety. Optional `init --pr-comment` generates a workflow
with explicit write permissions; it posts nothing itself and keeps the default
generated workflow's GitHub permissions read-only. See the [maintainer workflow](maintainer-workflow.md).
v0.24.0+ `init --workflow-only` leaves policy outside its read/write scope,
including under `--force`; it does not validate that policy. Selected linked,
reparse, shared or non-file initialization targets require manual setup. Exclusive
creation and opened-file checks reduce accidental writes, not all filesystem
races; initialization is not an atomic transaction and failed writes may leave
partial selected targets. Generated `@v0` is not necessarily the local CLI source.

The optional v0.24.0+ [guardrail completion command](guardrail-suggestions.md)
does not add keyword-based quality points. It checks only narrow deletion-policy
phrases in one selected file, offers a preview and requires content-bound
confirmation to append. Unrecognized text is review-needed, not proof of missing
safety; recognized wording is neither complete coverage nor enforcement. External
permissions, inheritance and arbitrary language semantics are outside this check.
Initial previews are read-only; append is explicitly requested, not an atomic
transaction, and may fail partially. Existing scoring and CI gates are unchanged.
Explicit example headings exclude their section; an open example section at EOF
requires manual merging. HTML-like tags disable policy interpretation for the
whole selected file. Narrow approval-bypass directives also require manual
resolution even alongside recognized protection; they are unscored review
signals, not complete conflict detection or evidence of actual agent behavior.

Unreleased source builds scope explicit guardrail selection without whole-tree
discovery. Only relevant ignore rules and the selected ancestry/parent names are
inspected for selection; unselected broken/external/nonregular instruction files
are not validated or repaired. Directory aliases/reparse ancestors and ambiguous
directory casing require manual integration. This does not change full scans or
doctor: an unsafe source elsewhere still stops the whole-tree check. Selected
review/append success is not a clean repository result. This refinement is not
in v0.24.0; confirmation and non-atomic append boundaries remain unchanged.

The scanner intentionally does not claim to understand arbitrary prose. These
inputs can still receive A 100 when they avoid every known deterministic rule:

- vague or useless instructions;
- harmful intent written without a recognized dangerous command;
- paraphrased contradictions whose directive bodies are not equivalent text;
- destructive tools and command forms that are not in the rule catalog;
- instructions that are syntactically valid but poorly matched to the repository.

Keyword-based “best practice” points are not added to hide these limitations;
they would be easy to game by copying phrases into a file. Broader semantic
judgment requires a separately evaluated model-assisted mode and a labeled
corpus, not a stronger marketing claim for the deterministic score.

The offline [Adversarial Benchmark v1](../benchmarks/adversarial-v1-report.md)
keeps both sides visible: 474/474 maintained deterministic contracts currently
match, while 6/8 labeled challenges are detected. The two remaining misses are
semantic cases. Fixing already-known false-reporting and environment-upload cases is development
progress, not an independent accuracy estimate.
The contract figure is a regression guarantee for a closed fixture suite, not a
real-world accuracy estimate.

There is also no completed independent comparison against direct AI review.
The [blinded review-comparison workflow](review-comparison.md) supports imported
model responses and held-out dataset declarations, but its bundled fixtures
are known synthetic calibration data with provisional labels. Missing answers
remain unreviewed, unresolved reference labels are excluded explicitly, and
unperformed AI runs are never presented as successful measurements.

## Appropriate use

Use AgentConfigScore to catch concrete regressions covered by its stable rule
catalog, review findings in CI, and keep accepted exceptions auditable. Do not
use it as the sole approval signal for generated code, repository security, or
instruction quality.

See the [real-repository smoke benchmark](../benchmarks/README.md) for pinned
public inputs. Real false positives, false negatives, and before/after cases are
especially valuable through the repository's **Real-world case** issue form.
