# Release acceptance and localization sequence

## Product boundary

The complete core milestone is a usable **deterministic instruction linter and
regression gate**: installation, safe setup, actionable findings, baseline policy,
local comparison, CI integration, reports and documented recovery paths.
It is not a promise to understand arbitrary Markdown or outperform AI review.
An optional semantic plugin is not required to complete this milestone.

## Automated release gates

Both ordinary CI and release acceptance exercise the installed wheel outside
the source checkout, without `PYTHONPATH` or user-site source fallbacks.

| Gate | Evidence |
|---|---|
| Source behavior | Full unittest suite; normal CI includes Python 3.10–3.14 and Linux/Windows/macOS |
| Distribution | Wheel + source distribution build; version agreement; no runtime dependencies |
| Installed user journey | Same offline acceptance script on Linux, Windows and macOS, including spaces and Unicode in repository paths |
| Useful pass/fail behavior | Clean and unchanged cases pass; known danger, deleted instructions and candidate-policy bypass attempts fail |
| Failure handling | Bad UTF-8 config and unwritable artifacts do not become successful scans |
| Publication ordering | Source tests and all installed-acceptance jobs must pass before GitHub release or PyPI publication |

The acceptance script checks both console aliases and the module entrypoint,
initialization dry-run/idempotency, doctor, rules, scan/report formats, feedback,
empty history, `diff`, `compare`, suppression ownership and temporary-worktree
cleanup. It uses only synthetic files and disposable local Git repositories;
it does not execute instruction text, call a model, or contact maintainers.

To reproduce after building and installing a wheel in a separate environment:

```bash
python scripts/verify_installed_package.py --python /path/to/wheel-env/bin/python --expected-version PACKAGE_VERSION
```

On Windows, use the environment's `Scripts/python.exe`. This is a development
script, not an extra runtime dependency or an installed user command.

## Before cutting the next package

- Check CI for the **exact commit** to publish; earlier green or red runs are
  historical evidence, not the current result.
- Verify version agreement in `pyproject.toml`, package `__init__.py` and
  `CITATION.cff`, and update the changelog before dispatching a release.
- Keep the user guide's development-only notes synchronized with what is
  actually on PyPI and `v0`; merging a PR alone does not update either.
- Review changes to stable rule IDs, JSON fields, scores and exit behavior.
  Treat a contract change as a documented compatibility change.
- Do not present maintained fixture counts, the unresolved AI pilot or failed
  source acquisitions as real-world accuracy or user feedback.

The release workflow is manual. Running tests or merging a readiness PR does
not create a tag or publish to PyPI. This document is a gate definition, not an
assertion that all future release steps have already been performed.

## Next milestone: optional Chinese documentation

After the core package is cut, add a lightweight language switch in each README:
English (default), 简体中文 and 繁體中文. The approach follows
[Transformers' multilingual README](https://github.com/huggingface/transformers/blob/main/README.md)
without adding a documentation framework or runtime translation dependency.

Planned files:

- `README.zh-CN.md` and `README.zh-TW.md`, with reciprocal language links.
- `docs/zh-CN/` and `docs/zh-TW/` versions of the user guide, limitations and
  configuration / suppression guidance first; advanced reference pages follow.
- A translation maintenance note recording the English source revision and
  explicitly identifying untranslated pages instead of linking empty placeholders.

Rules for the translation stage:

- Choosing a language is optional; English remains the default package README.
- Translate explanations, not command names, rule IDs, JSON keys, config paths,
  schema fields or executable examples. CI integrations must not depend on locale.
- Translate the limitations with the setup guide. Chinese documentation does
  **not** mean Chinese instruction semantics are supported by English prose rules.
- Review Simplified and Traditional wording separately; do not treat a blind
  character conversion as a complete technical translation.
- Do not add a CLI `--language` option until terminal-output localization is
  explicitly in scope and independently tested. Documentation is the first stage.

The translated files and language selector are planned, **not shipped yet**.
Real-user feedback and independent evaluation remain separate ongoing work;
they are not replaced by localization or release acceptance.
