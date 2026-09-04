# What the score does—and does not—mean

AgentConfigScore is a deterministic linter and regression gate for persistent
coding-agent instructions. Its score measures detected, rule-defined risks. It
does not measure whether an AI agent is intelligent, whether a prompt will solve
a task, or whether an instruction file is generally “good.”

**An A 100 result means that no active deterministic rule matched. It is not a
semantic quality certification.**

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
keeps both sides visible: 74/74 maintained deterministic contracts currently
match, while 0/8 labeled semantic and unmodeled danger challenges are detected.
The contract figure is a regression guarantee for a closed fixture suite, not a
real-world accuracy estimate.

## Appropriate use

Use AgentConfigScore to catch concrete regressions covered by its stable rule
catalog, review findings in CI, and keep accepted exceptions auditable. Do not
use it as the sole approval signal for generated code, repository security, or
instruction quality.

See the [real-repository smoke benchmark](../benchmarks/README.md) for pinned
public inputs. Real false positives, false negatives, and before/after cases are
especially valuable through the repository's **Real-world case** issue form.
