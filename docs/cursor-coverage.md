# Review Cursor coverage across existing files

**Available in v0.25.0+.** Install the package in a virtual environment to use
`scope coverage`. This extends the bounded [Cursor profile](cursor-scope.md).

A rule's glob can change while its instruction text and standalone score stay
unchanged. A task containing both an API file and a matching frontend file can
still receive the rule. An API-only task may lose its predicted attachment.
Coverage checks each inventoried file as an independent single-file context.

## Two trees or a local Git baseline

```bash
agent-config-score scope coverage ../repo-base . --under src --fail-on-lost-directives --fail-on-unknown
agent-config-score scope coverage --base-ref origin/main --path . --under src --fail-on-lost-directives --fail-on-unknown --json
```

Git mode pins the resolved local baseline commit, includes uncommitted working
tree changes, and cleans up its temporary baseline worktree on completion or
failure. It never fetches. Review the tool revision and CI invocation separately
from the PR being checked.

Repeat `--under` for multiple relative directory prefixes. Default `.` selects
the filtered tree. Prefixes respect directory boundaries, so `src` excludes
`src-other`. Prefixes and review flags are caller-owned, separate from normal
score policy and suppressions.

## Inventory and capture

The inventory is the union of regular, nonalias file paths on either side,
including untracked files. Each row retains `present_in_base` and
`present_in_head`. Added and deleted target names are modelled logically on
both sides. Their presence flags help identify file migrations. No task relevance
or target contents are inferred.

Dependency/admin directories named in `file_inventory.skipped_directory_names`
are pruned. File symlinks, directory symlinks/junctions and nonregular files are
excluded with counts. Build/dist/target/.next names remain eligible because
repositories can keep source there. Git ignore rules and instruction discovery
ignores do not filter target names. Instruction discovery still applies its own
ignores and whole-tree supported-source preflight.

Inventory reads names and metadata. Instruction sources are captured once per
side for activation and directive evidence, then reused across contexts. Both
sides must identify the same tool source. Keep trees stable while running;
capture and inventory do not form an atomic filesystem snapshot.

## Report and decisions

JSON retains inventories/exclusions, both rule source manifests and per-file
contexts. Source manifests include hashes, metadata/body line numbers, modes and
reasons. Raw globs, descriptions and directive bodies are omitted. Paths and
hashes remain potentially identifying information.

Each context includes baseline-active identities, retained identities,
recognized losses/gains, unknown sources and source lines for lost directives.
Summary `recognized_active_losses` counts directive-context pairs. One directive
lost for three files counts three times, without implying three vulnerabilities.

- Normal rule renames and another active copy can preserve an exact directive.
- Manual/model selection, unsupported metadata and potentially active opaque
  bodies remain unknown, separately from definite recognition losses.
- Files without recognized baseline-active directives are counted explicitly.
  A completed comparison cannot establish adequate instructions for those files.
- Joint tasks can have different attachment. Use `scope compare --target ...
  --target ...` to model a particular multi-file task.

Completed advisory analysis returns `0`. `--fail-on-lost-directives` returns `1`
for a recognized loss in any selected context. `--fail-on-unknown` separately
returns `1` for uncertain activation/body on either side.

Empty selections, invalid/nonportable paths, source/inventory failures,
tool-identity mismatch and resource limits return `2`, with no partial success
JSON. The union is limited to 2,048 file names. A conservative 100,000-unit budget
counts files multiplied by rules, recognized directive occurrences and possible
opposing-directive pairs. Narrow `--under` when needed. Large inputs fail instead
of silently sampling or truncating coverage.

## Replay the installed tool

From a repository checkout with v0.25.0+ installed in the selected Python:

```bash
python scripts/run_cursor_coverage_demo.py --output cursor-coverage-demo.json
```

Use `--python /path/to/env/python` to select another installation. The runner
invokes the installed module with isolated Python flags from outside the source
tree. Existing output files are preserved. It checks these five synthetic cases
and a joint-context control, retains fixture hashes and tool identity, and checks
that every standalone scan still scores 100.

| Candidate | Files with recognized loss | Files with unknown scope/body | Strict exit |
| --- | ---: | ---: | ---: |
| `narrowed` | 1, API file | 0 | 1 |
| `repaired` | 0 | 0 | 0 |
| `renamed` | 0 | 0 | 0 |
| `uncertain` | 0 | 2 | 1 |
| `base` unchanged | 0 | 0 | 0 |

The instruction body stays identical across the trees. API/frontend files exist
in each fixture. CI replays the example with an installed wheel on Linux,
Windows and macOS and retains JSON as `cursor-coverage-demo-<OS>` artifacts for
seven days. These are development controls with no independent accuracy estimate.

## CI setup and review artifacts

In v0.26.0+, initialize a reviewed coverage workflow without a source checkout:

```bash
agent-config-score init --coverage-under src --dry-run
agent-config-score init --coverage-under src
```

Repeat `--coverage-under` for other directories. Existing integrations can use
`--workflow-only --coverage-under src --force --dry-run` before explicitly
replacing their workflow. Workflow-only mode leaves policy outside its reads
and writes. `--force` replaces selected files, including local customizations.
The [copy-ready recipe](../examples/cursor-coverage.yml) is also available.

The default workflow is read-only. It combines the usual baseline-governed
score comparison with the Action's opt-in `coverage-under` input, strict
loss/unknown coverage, a job summary and seven-day artifacts. Completed review
failures retain their JSON and Markdown. Input/read failures expose exit `2`
and an unavailable summary, without a completed coverage artifact.

The generated workflow verifies that its selected Action actually supplies the
coverage outputs. Pin an Action revision supporting these inputs, such as
`LE0-Lin/AgentConfigScore@v0.26.0`. An older Action cannot silently skip the
requested coverage. Prefixes and coverage gates remain caller-owned.

For local readable review evidence:

```bash
agent-config-score scope coverage --base-ref origin/main --under src --fail-on-lost-directives --fail-on-unknown --markdown coverage-review.md --json
```

`--markdown` is additive in v0.26.0. Completed exit `1` still writes the review.
A write failure uses exit `2` with no successful JSON. Choose artifact paths
outside instruction/policy files. Report writes are not atomic transactions.
Review the cited metadata/directive lines, repair the intended attachment or
approve a scope migration through normal review, then rerun the same command.

The real composite Action is exercised on disposable Git fixtures for
narrowing, repair, rename, unknown loading, unchanged inputs, empty selection
and unreadable source. Acceptance checks the actual step outcome, failure
outputs, completed reports and worktree cleanup before release publication.
These are development controls with no native Cursor or user-adoption claim.

## Native Cursor verification boundary

The profile interprets the published [Cursor rules documentation](https://cursor.com/docs/rules),
checked on 2026-11-10. This example supplies no native Cursor capture.
`observed_agent_context` remains false. A native check must record the Cursor
version, matching inputs and observable attachment evidence, and retain
disagreements. Model answers alone cannot certify which rules were attached.
Current results establish behavior of the static model and installed tool.
