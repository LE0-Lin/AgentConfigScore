# Optional documentation languages

[English](../README.md) | [简体中文](../README.simplified.md) | [繁體中文](../README.traditional.md)

English is the default repository entrypoint and package README. Choosing a
different document language does not change CLI output, rule grammar, scores,
configuration version, command names, JSON keys or API behavior. There is no
runtime `--language` option. Chinese instruction semantics are not certified by
providing Chinese documentation.

## Available scope

| English source | 简体中文 | 繁體中文 | Scope |
|---|---|---|---|
| [README](../README.md) | [Overview](../README.simplified.md) | [Overview](../README.traditional.md) | Localized core overview, not the entire long English reference |
| [User guide](user-guide.md) | [Guide](simplified/user-guide.md) | [Guide](traditional/user-guide.md) | Core user journey, all executable examples, exit codes and troubleshooting |
| [Limitations](limitations.md) | [Limits](simplified/limitations.md) | [Limits](traditional/limitations.md) | Core score contract, rule limits and unestablished accuracy; historic table/manual links stay in English |

Advanced Action inputs/outputs, precise rule grammars, score-history integrations,
release notes, contribution instructions and research protocols remain English.
Localized pages identify those links as English instead of creating empty pages.
The two Chinese variants are maintained with Simplified and Traditional regional
wording rather than changing the program's machine-readable identifiers.
Documentation paths use `simplified` and `traditional` to describe the script
variants rather than a region.

## Source baseline and maintenance

The first localized core pages use English source revision
`78af3f9a470c9edab67f3d1579e8319a299bb191` (v0.23.0). The repository language
links are a subsequent documentation update; they are not inside the immutable
v0.23.0 PyPI distributions or v0.23.0 tag.

On 2026-10-11, both limitation summaries were reviewed together with the English
path-reference changes built on source revision
`38bc911273b449e4a23287540767c9ca70108c65`: conditional references, repository
roles, path-index/discovery separation, symlink and host-case limits. This is an
unreleased synchronized source update, not a change to the original v0.23.0 tag.

On 2026-10-14, both guides and limitation summaries were reviewed together with
the English explicit-relative-path and index-I/O changes built on source revision
`ef733582a47233c96cdc76b0017b9880f415e5da`. The existing root/AGENTS scope
interpretations remain, arbitrary suffix substitution is disabled for explicit
relative references, and index read failures stay operational/doctor errors.
Commands and the published v0.23.0 artifacts remain unchanged.

On 2026-10-15, both guides and limitation summaries were reviewed with the English
instruction-source containment/readability changes built on source revision
`7ced98d3c4569bb21dcdbb83b48f948d8abe9a3c`: internal file aliases, pruned directory
aliases, operational failures, doctor readability checks, legacy `read-error`,
and explicit non-atomic/non-sandbox boundaries. Published artifacts are unchanged.

On 2026-10-19, both guides and limitation summaries were reviewed with the English
report-identity changes built on source revision
`f806695337119d21dac486b2aa7a6133b945dfdb`: captured version/source metadata,
unknown-source behavior, additive compatibility and non-attestation limits. The
new detailed format reference remains English. Published artifacts are unchanged.

On 2026-10-23, both guides and limitation summaries were reviewed with the English
regression-source/move changes built on source revision
`706a2a61140f847f4e88a8cf54702e2cd2424f3e`: captured input reuse, one-to-one exact
same-directory moves, review of scope changes, raw-source privacy and unchanged
numeric scoring/policy defaults. The detailed coverage reference remains English;
published artifacts and frozen research evidence are unchanged.

Also on 2026-10-23, both core guides/limitations were synchronized for the opt-in
deletion-safeguard review built on `09d614d093a67b14bcca294f008e794920516a4f`:
selected-file evidence, read-only previews, explicit content-bound append
confirmation, three addition-template languages and privacy/non-atomic limits.
`--template-language` selects proposed text only; it is not CLI localization or
general Chinese semantic support. The detailed reference remains English.

The next guardrail refinement on 2026-10-23, built on
`ed68d4714a153fa8a2634fe0972d55705101124d`, was reviewed in both core guides and
limitation summaries: explicit example-section exclusion, manual-only open
example sections and HTML layouts, and unscored approval-bypass review signals
that block automatic append without claiming general conflict detection.
Executable examples, scoring defaults and published artifacts remain unchanged.

Also on 2026-10-23, both core guides/limitations were reviewed for the maintainer
workflow built on `ffbf7f13a627634b4ca9b72e9c58f58e84027317`: opt-in explanatory
text/Markdown, unchanged scores/JSON, static non-scored guidance, explicit PR
comment write permissions, no-overwrite defaults and fork/revision boundaries.
New detailed maintainer/checklist references remain English and are linked from
both variants. Executable guide examples remain identical; published artifacts
and frozen research evidence are unchanged.

The subsequent workflow-only refinement on 2026-10-23, built on
`6e665dbb8dc2491cb0ea992c9af0776058413f00`, was synchronized across both core
guides/limitations: exact policy preservation by excluding it from initialization,
explicit workflow-only overwrite scope, selected-target alias/write boundaries,
non-atomic failure limits and disclosure of the unchanged generated Action ref.
Executable guide examples remain identical; advanced details stay in the English
maintainer guide. Published artifacts and frozen research evidence are unchanged.

For v0.24.0 on 2026-10-23, built on
`5e3ef04bfbba538eacfcad0a3830778830124844`, both core guides/limitations were
reviewed for release availability of report identity, tightened regression
checks, opt-in guardrails, explanations and scoped workflow setup. Both overview
Action examples pin `v0.24.0`. This is the first release tag containing these
repository translations; the English package README links to them, but the wheel
does not bundle offline documentation or translated terminal messages. Earlier
sync notes describe their historical state; the v0.23.0 artifacts and frozen
research records remain unchanged.

After v0.24.0 on 2026-10-23, built on
`5d00ab1d5ce64f88fa392df1d0ba396bca98f8de`, both limitation summaries were
synchronized for the bounded reference-link check: document-local definitions,
first-definition precedence, definition-line reporting, unused-definition/caption
handling and unsupported Markdown/code/layout boundaries. This is an unreleased
source update, not a change to v0.24.0 packages, tags, rolling Action refs or
frozen research evidence. Executable guide examples are unchanged.

On 2026-10-24, built on `8c1747be614a79692d07882d2c7841fb0ad83543`, both core
guides and limitation summaries were synchronized for scoped guardrail file
selection: no whole-tree traversal, relevant ignore/ancestor checks, manual-only
directory aliases/case ambiguity and unchanged full-scan/doctor failure behavior.
This is unreleased source behavior, not a v0.24.0 artifact change. Executable
guide examples, scoring, confirmation and append boundaries remain unchanged.

On 2026-10-25, built on `10e9b50a6f507ae9edf7a1589fdca704d05cfc07`, both core
guides and limitation summaries were synchronized for strict policy JSON:
duplicate decoded names at every depth, non-standard numeric constants, Boolean
format-version rejection, one-read doctor metadata and unchanged missing-config
defaults. Invalid baseline/candidate configs remain operational failures even
under CLI threshold overrides; validation is not policy adequacy or an atomic
snapshot. This is unreleased source behavior, not a v0.24.0 artifact or Action-ref
update. Executable examples, valid-policy scoring and frozen research are unchanged.

When an English source page changes, review both variants together and record
the new source revision here. Preserve executable examples, rule IDs and JSON
keys verbatim. Keep the score limitations and failure/exit semantics aligned;
do not translate a prohibition into an affirmative command. Mark any partial
coverage clearly and retain links to the English reference.

Tests verify language-link targets, guide code-block parity, identical config
and workflow examples between variants, and English as the default package
README. They cannot verify translation meaning or serve as independent human
review. Wording and rule interpretation still need review when sources change.
