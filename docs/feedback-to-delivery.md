# Public maintainer feedback and delivered behavior

In [issue #46](https://github.com/LE0-Lin/AgentConfigScore/issues/46),
JasonLandbridge described four capabilities he would find useful. This is
public, externally authored **requirements feedback**. It establishes the
origin of a request. External installation, sustained use, measured time saved
and maintainer-confirmed effectiveness remain unverified.

| Requested capability, paraphrased | Delivered surface | Verification and boundary |
|---|---|---|
| Check whether instruction-file references remain valid | `dead-path`, Markdown link resolution, repository/scope path checks | Released checks have deterministic tests. The [new path case study](path-case-study.md) adds a generated-output correction and explicit relative-directory handling in unreleased source. Generated and package-relative ambiguity remain bounded. |
| Give practical instruction-file guidance | [Advisory checklist](best-practices.md), [maintainer workflow](maintainer-workflow.md), opt-in [safeguard review](guardrail-suggestions.md) | Documentation and narrowly recognized review suggestions are available. They do not constitute a general semantic reviewer or a scored best-practice certification. |
| Surface prompt-injection concerns | The released `prompt-injection-override` warning and its conservative context handling | The rule targets explicit prior-instruction override phrases. It does not detect arbitrary injection attacks or enforce agent behavior. |
| Make review results visible on PRs | [Opt-in single-comment workflow](pr-comments.md), including generated setup via `init --pr-comment` | The repository's CI and integration tests validate the maintained recipe. A caller explicitly grants comment permission. Adoption by the requester's repository is not established. |

## How to use this evidence

The defensible project story is a concrete feedback loop: a public maintainer
requested review features; corresponding interfaces were implemented; the
project retained acceptance tests, versioned releases and limits; real source
inputs then exposed scanner errors that required further maintenance.

The [path replay](../benchmarks/path-check-v2/README.md) makes one of those
maintenance changes inspectable without executing upstream commands or asking
another maintainer to confirm an obvious sentence. It preserves failed attempts
and the final conservative scope. It remains project-authored development
evidence.

Independent reference labels, a matched AI comparison and externally observed
workflow outcomes are separate open evidence gaps. This document does not turn
a feature request, a GitHub star or a project-maintained test suite into a user
success metric. It makes the existing request and implemented response easy to
verify directly.
