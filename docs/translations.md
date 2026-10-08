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

When an English source page changes, review both variants together and record
the new source revision here. Preserve executable examples, rule IDs and JSON
keys verbatim. Keep the score limitations and failure/exit semantics aligned;
do not translate a prohibition into an affirmative command. Mark any partial
coverage clearly and retain links to the English reference.

Tests verify language-link targets, guide code-block parity, identical config
and workflow examples between variants, and English as the default package
README. They cannot verify translation meaning or serve as independent human
review. Wording and rule interpretation still need review when sources change.
