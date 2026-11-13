# A generated file should not become a broken-path warning

This case shows a concrete scanner failure on a public project's instructions,
the correction, and a regression caught while implementing it. It is a
maintainer development case with reproducible source evidence; it does not
establish external adoption or independent detection accuracy.

## The user's review problem

An instruction file can mention checked-in source, a required directory, and a
file that appears only after a build. Reporting every absent name as a broken
reference makes a CI report noisy. Ignoring all paths near the word "generated"
could instead conceal a missing generator or an unrelated required source file.

At [the pinned Vitest revision](https://github.com/vitest-dev/vitest/blob/f4fdbcae08ec365f35d9e1866ce3e7d04880ea60/AGENTS.md#L201),
the document declares that `docs/.vitepress/contributor-names.json` is generated
by `pnpm docs:contributors`. The published ACS v0.26.1 warns about that absent
output in an unbuilt checkout. The retained package script and producer source
confirm the exact write target; the audit never runs the upstream command.

## Correction and an observed failure

The changed scanner recognizes a bounded output declaration attached to that
single prose reference. It continues checking the generator's source path,
actual Markdown link destinations, dangerous commands and credentials. A
general generated-files heading does not exempt later references, and a
conditional or unfinished sentence does not satisfy the grammar.

The same maintenance pass explores checks for quoted directories ending in `/`.
The first real-source replay then catches a regression in this new rule:
Vitest uses bare `dist/` as a package export/build-output location, and the
scanner incorrectly demands a root directory. The known-negative gate fails.
That failing report is retained. Bare output names are subsequently excluded;
explicit paths such as `./dist/` still request an existence check. A wider
inspection then finds package `lib/` outputs and Husky's install-time directory.
The final rule requires an explicit `./` or `../` prefix for directory prose;
unprefixed directory names stay unresolved instead of accumulating exemptions.

## What the completed replay establishes

| Check | Frozen published version | Changed source |
|---|---|---|
| Generated contributor file | Warning | Warning removed |
| Eight independently applied target-removal controls, original wording | 3 detected | 3 detected |
| Original 16 selected natural occurrences | 0 flagged | 0 flagged |

Four separate controls explicitly prefix the directory literal with `./` before
removing its target. Both the wording and inventory change; those controls are
kept separate from the original eight. Unprefixed directory names remain outside
the conservative prose heuristic. Sixteen correlated selected occurrences
cannot establish general precision, and these development controls cannot
establish independent recall.

The [raw results, failed attempt, source hashes and offline reproduction](../benchmarks/path-check-v2/README.md)
allow readers to inspect the unfavorable observations as well as the fixes.
The complete source suite and installed-package CI check other formats and
operating systems separately. The names-only replay itself uses Linux because
some retained repository trees require a case-sensitive filesystem.

## Apply the result

The implementation is currently **unreleased source**, separate from the
published v0.26.1 wheel. From a reviewed checkout, install with
`python -m pip install .` and run ordinary ACS scans/comparisons. A passing
result means the selected deterministic checks passed; the generated-output
declaration is not authenticated and no upstream build is executed.

For a directory intended to exist at a concrete location, use `./` or `../`
with a trailing slash. For an output that may be absent before
a build, state its producer clearly. Actual Markdown links continue to require
their destinations. The [documented path grammar](limitations.md#plain-prose-path-references)
defines the exact supported forms and remaining ambiguity.

This gives a user-reviewable engineering result: fewer known noisy warnings,
additional explicit directory coverage, and a demonstrated failing gate during
development. External users' sustained workflows and independently adjudicated
accuracy remain open validation work.
