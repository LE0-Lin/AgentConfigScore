# What the score does—and does not—mean

AgentConfigScore is a deterministic linter and regression gate for persistent
coding-agent instructions. Its score measures detected, rule-defined risks. It
does not measure whether an AI agent is intelligent, whether a prompt will solve
a task, or whether an instruction file is generally “good.”

**An A 100 result means that no active deterministic rule matched. It is not a
semantic quality certification.**

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
repository are skipped. Reference-style links and nested parentheses in link
destinations are not currently parsed. This is a limited link check, not a full
Markdown validator. Plain prose path heuristics retain their existing behavior.

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

Each hardened case has an automated regression test. Exact file moves are not
reported as deletion, and baseline-owned suppressions can document an intentional
exception.

## Known blind spots

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
