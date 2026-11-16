# Local-link target-existence pilot

**Completed, with insufficient natural coverage for an accuracy estimate.**
The frozen published ACS **0.26.2** wheel checked two selected links from
previously unused evaluation repositories. Both targets exist and neither
produces a matching warning. Removing each target separately produces a warning
in both cases. These are two natural negative cases and two synthetic positive
controls, not four independent real-world cases.

| Track | Cases | TP | FP | TN | FN |
|---|---:|---:|---:|---:|---:|
| Unmodified selected local links | 2 | 0 | 0 | 2 | 0 |
| Separately removed targets | 2 | 2 | 0 | 0 | 0 |

Natural missing-target recall and warning precision are **unavailable**, because
there are no natural missing targets and no natural warnings. Do not present
the controls' success as general accuracy or combine the tracks into a headline
percentage. Four of the registered maximum six controls could not be acquired;
there was no replacement or outcome balancing.

## What was measured

The question is deliberately mechanical: does a repository-local Markdown link
resolve to a tracked target relative to its document in a pinned, unbuilt Git
snapshot? An absent snapshot target is not proof of an upstream defect: it may
be generated, an example, or intentionally unavailable. No semantic safety,
usefulness, author intent, or comparison with AI is measured.

The [protocol](protocol.json) was committed as
`9fa95f2927048b78d885e76320152f787c82605b` before source acquisition.
The [collection record](collected/collection.json) retains every exclusion,
revision, source URL, byte hash, license notice, and reference fact before ACS
predictions. The independent [markdown-it-py CommonMark parser](https://markdown-it-py.readthedocs.io/en/latest/using.html)
extracts link tokens; the reference resolver uses Git names, not ACS's path
extractor or its warning output. Git tree objects and source blobs are verified.
The parser and ACS package wheels are separately version/hash pinned in the
[study requirements](../../scripts/requirements-link-study.txt).

Eight repositories were registered without replacement:

| Repository | Collection outcome |
|---|---|
| microsoft/TypeScript | Recursive tree truncated; excluded |
| eslint/eslint | Root AGENTS.md, one selected link |
| rust-lang/cargo | No regular instruction file with a registered name |
| psf/requests | No regular instruction file with a registered name |
| cli/cli | Root AGENTS.md, one selected link; 17 multiline-block link occurrences excluded |
| golang/go | GitHub license identifier NOASSERTION, outside registered allowlist |
| neovim/neovim | GitHub license identifier NOASSERTION, outside registered allowlist |
| rails/rails | Root AGENTS.md retained, no eligible link |

This reveals a limitation in the sampling method: requiring one-line inline
blocks excluded many ordinary wrapped links, and the repository/license rules
also reduced coverage. A broader future study needs a new declared selection
rule. Changing these exclusions after seeing results would not improve this
study's evidence. No new source or rule was substituted to make it look larger.

## Inspect or reproduce

The retained [raw result](result.json) comes from the
[successful Linux execution](https://github.com/LE0-Lin/AgentConfigScore/actions/runs/43824776986)
at runner checkout `7c227f07f673d92bdefbc3a47c3a70a352764b78`.
Its installed source fingerprint is
`5cd84e53c40b581b70edbbee36f868f23b32a25bb40b7186a8841ddca8267cc9`.

On Linux with a case-sensitive temporary filesystem, from the repository root:

```bash
python3 -m venv /tmp/acs-link-study
/tmp/acs-link-study/bin/python -m pip install --require-hashes --only-binary=:all: -r scripts/requirements-link-study.txt
/tmp/acs-link-study/bin/python -m unittest discover -s scripts -p test_link_study.py -v
/tmp/acs-link-study/bin/python scripts/run_link_study.py replay --output /tmp/acs-link-study-new-result.json
```

Package installation needs network access; replay uses retained local evidence
and makes no network requests. Do not install the checkout into this environment:
the subject is the frozen public wheel. Six method checks exercise code/fence
exclusions, reference links, URL decoding, alias abstention, relative resolution,
and deterministic document selection. They check the measurement method, not
independent correctness of ACS.

The runner creates a complete names-only tree projection with exact selected
instruction bytes and empty other regular files. It omits symlinks/gitlinks and
excludes candidate resolutions that depend on them. Discovery is explicitly
scoped to that single document; no native whole-repository equivalence is
claimed. Prediction is a matching destination warning in the document; precise
source-line localization is not scored. Full findings are retained, including
findings outside the selected cases, which remain unlabelled.

The optional `collect` command requires authenticated `gh`, downloads public
source data, and writes a **new** directory. Running it now acquires different
default-branch revisions; it cannot reproduce this snapshot's collection.

This is a maintainer-run component pilot with an independent reference parser,
**not independent human evaluation or external user adoption**. No maintainer
was contacted for these samples and no upstream command was executed. The
earlier human review study remains uncompleted. Future changes informed by this
corpus make it development data and require fresh data for validation.
