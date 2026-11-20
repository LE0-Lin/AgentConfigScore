# Maintainer feedback to delivered features

In [issue #46](https://github.com/LE0-Lin/AgentConfigScore/issues/46),
JasonLandbridge listed four capabilities he wanted from an instruction linter.
The table below maps those requests to what is currently shipped and where the
boundaries remain. (This tracks requirements feedback—not external adoption or
measured time saved.)

| Requested capability | Shipped surface | Scope and limits |
|---|---|---|
| Check whether referenced paths stay valid | `dead-path`, local Markdown inline/reference links, explicit relative directory checks, generated-output and inline-code example handling | Deterministic rules with regression tests and a [public-source case study](path-case-study.md). Unprefixed directories and arbitrary build outputs stay conservative. |
| Give practical instruction-file guidance | `--explain` next steps, [best-practice checklist](best-practices.md), [maintainer workflow](maintainer-workflow.md), opt-in `guardrails` | Static review advice and narrow deletion-safeguard checks—not a general semantic reviewer or keyword-scored quality grade. |
| Surface prompt-injection concerns | `prompt-injection-override` with conservative prohibition/example context handling | Targets explicit override phrases; does not detect arbitrary paraphrases or runtime tool-output injections. |
| Make results visible on PRs | Opt-in single PR comment workflow (`init --pr-comment` / `examples/pr-comment.yml`) with per-rule breakdown and recheck commands | Tested in CI against a fake GitHub client; caller explicitly grants comment permissions and forks remain read-only ([PR comments](pr-comments.md)). |

Open evidence gaps—independent human reference labels, a matched AI comparison,
and observed external adoption—remain tracked separately in
[review-comparison.md](review-comparison.md) and
[benchmarks/path-check-v2/README.md](../benchmarks/path-check-v2/README.md).
