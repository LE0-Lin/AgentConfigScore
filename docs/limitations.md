# What the score does—and does not—mean

English | [简体中文](simplified/limitations.md) | [繁體中文](traditional/limitations.md)

AgentConfigScore is a deterministic linter and regression gate for coding-agent
instruction files. Its score reflects matches against a fixed rule catalog. It
does not measure model intelligence, task success, or overall prompt quality.

**An A 100 means no active rule matched. It is not a semantic quality or safety
certification.**

A few general boundaries apply across the whole tool:

- **Static, local analysis:** ACS never calls an AI model, fetches URLs, or
  executes commands found in instruction files.
- **Not a filesystem sandbox:** source, config, and path checks catch broken
  links and out-of-root escapes on a stable checkout, but are not atomic
  against concurrent writes or hostile filesystems.
- **Provenance:** reports include the tool version and source SHA-256
  fingerprint ([report identity](report-identity.md)) to identify the build, not
  to certify inputs or accuracy.

## What can still score A 100

Any file that avoids the active deterministic rules can score 100, including:

- vague or unhelpful instructions (for example, `"Do a good job."`);
- harmful intent phrased without a recognized dangerous command or prose form;
- paraphrased contradictions whose directive bodies do not match exactly;
- destructive tools or shell forms outside the rule catalog;
- syntactically clean instructions that do not match the actual repository.

We intentionally avoid awarding keyword-based “best practice” points, which are
easy to game. Broader semantic review belongs in a separately evaluated
model-assisted workflow.

## Configuration, history, and filesystem boundaries

- **Strict JSON config:** `.agentconfigscore.json` rejects duplicate keys at any
  depth, `NaN`/`Infinity`, and Boolean `version`. It must resolve to a regular
  file inside the repository root; dangling, cyclic, external, or unreadable
  configs fail with exit `2` (`doctor` exits `1`) instead of falling back to
  defaults ([doctor](doctor.md#configuration-decoding)).
- **Local score history:** `history` treats a damaged or unreadable index as
  exit `2` rather than an empty success. The append helper replaces the file
  instead of truncating it, and expects serialized writers
  ([score history](score-history-cli.md)).

### Instruction-file filesystem boundary

Selected instruction files and `.agentconfigscoreignore` must resolve to regular
files inside the scan root. Internal file symlinks are supported (findings and
relative links use the discovered alias's location). Discovery does not descend
into child directory symlinks or Windows junctions, and prunes excluded
dependency/build trees and `/**` ignore subtrees before descent.

Dangling, cyclic, external, non-regular, or unreadable selected sources abort
scans, `compare`, and `feedback` with exit `2` (`doctor` reports an
`instructions` error and exits `1`) without echoing raw target paths. Legacy
`read-error` remains in the catalog only for historical report/suppression
compatibility.

## Command interpretation

`rm-rf`, `git-clean-force`, and `docker-system-prune` tokenize bounded shell
fragments (up to 1,000 characters, supporting reordered/split/long flags,
backslash line continuations, and quoted option values) and stop at shell
separators or `--`. Git dry-run/interactive modes are excluded, a later
interactive flag overrides `rm -f`, and filter/exclude values are not treated as
flags. Options after ordinary operands, shell variables, aliases, wrappers, and
global options before subcommands are not resolved.

A shared document-context pass lets narrowly recognized prohibition labels cover
an immediately adjacent closed code fence or contiguous command list. Unlabeled
code remains active, unclosed fences do not inherit prohibitions, and literal
credentials are always checked independently
([instruction context](instruction-context.md)).

Option semantics follow the [Git clean manual](https://git-scm.com/docs/git-clean),
[GNU rm manual](https://www.gnu.org/software/coreutils/manual/html_node/rm-invocation.html),
and [Docker prune reference](https://docs.docker.com/reference/cli/docker/system/prune/).

## Prompt-injection warnings

`prompt-injection-override` flags explicit English override phrases such as
`ignore previous instructions`. Explicit prohibitions, whole-line labeled
examples (`Attack example: "ignore previous instructions"`), and adjacent
prohibited instruction blocks are excluded; quotes or code fences alone are not.
More elaborate educational examples can still trigger warnings—review and add a
reasoned suppression if needed. Arbitrary paraphrases, other languages, and
runtime tool-output injections are out of scope.

## Prose safety rules

- **`false-success-report`:** requires a single-sentence English directive to
  conceal errors while reporting success, or an English or Simplified/Traditional
  Chinese directive claiming tests passed despite failure or without running
  them. Prohibitions, quotes, code examples, and merely skipping tests do not
  trigger it ([verification reporting](verification-reporting.md)).
- **`deletion-approval-bypass`:** requires an explicit English or Chinese prose
  directive combining deletion of a production database or existing/user files
  with an attached approval bypass. Authorized or disposable cleanup,
  prohibitions, and examples stay distinct
  ([deletion approval bypass](deletion-approval-bypass.md)).
- **`broad-environment-upload`:** requires a transfer verb, full environment
  source, and non-loopback network destination in one English clause. Names-only
  metadata, redaction, logs, prohibitions, and code examples are excluded
  ([environment upload](environment-upload.md)).

None of these rules combine evidence across sentences, inspect runtime behavior,
or catch arbitrary paraphrases.

## Local Markdown links

Inline links, images, and simple full/collapsed reference links (`[Guide][ref]`,
`[ref][]` with a same-file single-line definition) are resolved relative to the
instruction file's directory. URL-encoded spaces and angle-bracket destinations
are supported; fragment headings are not validated. Remote links, anchor-only
links, fenced/indented code, matched inline code spans, escaped opening
brackets, absolute paths, and out-of-root paths are skipped. Shortcut reference
links (`[ref]`), multiline definitions, container definitions, nested
parentheses, and HTML layouts are left to manual review.

## Plain prose path references

- **Explicit relative paths (`./`, `../`):** checked against the repository root
  and applicable instruction-directory bases (nested `AGENTS` files also check
  in-repository ancestors). They never pass via an unrelated package suffix.
  Single-backtick directories with `./` or `../` and a trailing `/` require a
  real directory; unprefixed names (`packages/`, `dist/`, `test/unit`) are not
  guessed.
- **Unprefixed file paths:** use conservative package-relative suffix lookup
  across the repository (including existing files under `build`, `dist`,
  `target`, and `.next`, while excluding dependency/admin trees and directory
  symlinks). Directory traversal errors stop the scan with exit `2` rather than
  producing a partial index.
- **Narrow non-required exemptions:** immediate closed `(if exists)` /
  `(if it exists)` notes, same-line passive generated-output clauses such as
  `` `docs/out.json` is generated by `make docs` ``, and two-component GitHub
  slugs (`owner/tool.js`) in explicit repository/remote roles skip only that
  prose reference. Actual Markdown links, generator paths, commands, and
  credentials stay checked.

ACS does not infer `cd` working directories or build generated artifacts;
case-sensitivity depends on the host filesystem.

## Cursor file-context profile

`scope`, `scope compare`, `scope diff`, and `scope coverage` predict automatic
attachment for root `.cursor/rules/` files from declared or inventoried paths
([cursor-scope](cursor-scope.md), [cursor-scope-impact](cursor-scope-impact.md),
[cursor-coverage](cursor-coverage.md)). Manual/model-selected rules and
unsupported bodies stay `unknown`, and opposing-directive checks use bounded
English grammar. These commands are unscored and do not observe Cursor at
runtime.

## Regression checks, `--explain`, and `guardrails`

- **Regression-only errors:** `no-config` and `empty-instructions` cap the grade
  below A, as does any active error. `instruction-file-removed` only exempts
  one-to-one exact-text moves to newly added supported files in the same
  directory. `directive-polarity-flip` and `contradiction` match exact directive
  bodies ([regression coverage](regression-coverage.md)). Enable
  `fail_on_new_errors` to block regression-only errors when both scores are 100.
- **`--explain` and `init`:** `--explain` adds static review advice only (no
  auto-fixes or score changes). `init --pr-comment` opts into
  `pull-requests: write`; default `init` stays read-only. `init --workflow-only`
  leaves `.agentconfigscore.json` untouched.
- **`guardrails`:** unscored, selected-file preview for deletion-approval
  wording; appending requires a content-bound confirmation token
  ([guardrail suggestions](guardrail-suggestions.md)).

## What benchmarks do—and do not—establish

- **Offline adversarial suite** ([report](../benchmarks/adversarial-v1-report.md)):
  474/474 maintained deterministic contracts match, and 6/8 labeled challenges
  are detected (the remaining 2 are semantic misses). This is a closed
  regression suite, not a real-world accuracy rate.
- **AI comparison** ([workflow](review-comparison.md)): no independent held-out
  human-adjudicated comparison against AI review has been completed yet.
- **Public-repo smoke checks** ([benchmarks](../benchmarks/README.md)): useful
  for catching real false positives, not a substitute for independent accuracy
  evaluation.

## Appropriate use

Use AgentConfigScore to catch concrete regressions covered by its rule catalog,
review changes in CI, and keep accepted exceptions auditable. Do not use it as
the sole approval signal for generated code, repository security, or instruction
quality.
