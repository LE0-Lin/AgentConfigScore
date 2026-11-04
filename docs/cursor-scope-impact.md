# Comparing Cursor attachment changes

**Unreleased.** Source builds after v0.24.0 extend the [Cursor file-context
profile](cursor-scope.md) with two entrypoints:

```bash
agent-config-score scope compare ../repo-base . --target src/api/service.py --json
agent-config-score scope diff origin/main --target src/api/service.py --json
```

`compare` reads two supplied repository trees. `diff` compares a local Git ref
with the repository's working tree, including uncommitted files. It retains the
resolved baseline commit and removes its temporary detached worktree on success
or failure. Omit the ref for conservative local default-branch detection; use
`--path REPOSITORY` outside the target repository. No ref is fetched.

Both sides use the **same** normalized `--target` set and activation profile.
Each selected source is captured once per side for both metadata and directive
evidence. Both trees must complete source preflight/reads. A changed tool-source
identity during comparison aborts instead of mixing implementations.

## Three distinct kinds of evidence

1. **Rule lifecycle:** added, removed or modified files, with before/after modes,
   activation reasons, metadata lines, original body lines and source hashes.
2. **Trigger changes:** which supplied paths stop/start matching. A rule may lose
   an API-file trigger but remain attached because another declared file matches.
3. **Recognized directive availability:** aggregate sources across the rules in
   each context. Renaming a rule or retaining the same directive in another
   active rule need not lose its recognized active availability.

Source hashes cover UTF-8 decoded, newline-normalized text of read `.mdc`
sources. Plain `.md` and unmodelled extension casing are not read and have null
hashes. Changed bodies/metadata can be visible even when their effect on the
supplied targets is unchanged. This is not an arbitrary-glob equivalence or
global narrowing proof; changes affecting undeclared files are outside the run.

An exact directive is identified by its existing normalized English body hash
and polarity. Original evidence keeps source paths and one-based line numbers.
Raw directive and metadata values are not exported. An identical hash is not
proof of semantic equivalence, safe behavior or authentic evidence.

| Availability | Meaning for this recognized directive and declared context |
|---|---|
| `active` | At least one recognized source is predicted automatically attached |
| `unknown` | No active source is established, and a matching source has unknown activation or a non-inactive rule body is uninterpreted |
| `inactive` | Recognized sources exist, all are predicted inactive, and no potentially active opaque body obscures the result |
| `not_recognized` | No source of this exact directive was recognized and no potentially active opaque body obscures the result |

Uninterpreted, potentially active bodies conservatively leave missing identities
unknown: the checker cannot establish whether they contain replacements. A
manual/model-selected rule with an interpretable body contributes uncertainty
to identities recognized in that body. Unsupported English paraphrases do not
establish equivalence. Rephrasing a directive can therefore require review even
if a human considers its meaning preserved.

`rule_changes` records file/activation/trigger changes. `directive_changes`
records changed availability or source evidence, including harmless line shifts
and moves whose availability stays `active_to_active`. Summary counts keep
baseline-active identities, retained identities, recognized losses/gains, unknown
rules and uninterpreted non-inactive bodies separate. Gains include newly
established active availability from unknown; they do not prove improvement.
Both full side reports and their tool identities are retained.

## Optional review gate

```bash
agent-config-score scope diff origin/main --target src/api/service.py --fail-on-lost-directives --fail-on-unknown --json
```

- Without flags, completed comparisons return **0**, including changes/unknowns.
- `--fail-on-lost-directives` returns **1** when a baseline-active identity becomes
  `inactive` or `not_recognized`. It does not equate unknown with definite loss.
- `--fail-on-unknown` returns **1** when **either** side has unknown rule activation
  or an uninterpreted non-inactive body. This also covers an uninspectable
  baseline, not just a newly uncertain candidate.
- Input, source, encoding, Git, pair-budget or identity-consistency failures use
  **2**, with no successful/partial JSON report.

Use both flags when uncertainty requires review. `review_gate` records the
chosen flags, failure reasons and decision. The flags belong to the caller;
existing repository score-policy JSON and suppressions do not configure this
profile. Review workflow/tool changes normally. This does not extend the
baseline-governed policy schema or alter normal scan/diff/Action defaults.

An empty recognized baseline protects zero directive identities. Exit 0 does
not imply that required safeguards exist. Neither flag blocks new opposing
directives automatically; side reports retain those separate review signals.
Full semantic conflicts, harmful unrecognized text and runtime enforcement
remain outside this gate.

## Source-build GitHub Actions example

```yaml
name: Cursor attachment review
on: [pull_request]
permissions:
  contents: read
env:
  ACS_TOOL_REVISION: SCOPE_IMPACT_TOOL_COMMIT
jobs:
  scope:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
        with:
          fetch-depth: 0
          persist-credentials: false
      - uses: actions/setup-python@v7
        with:
          python-version: "3.12"
      - name: Install the reviewed tool source
        run: python -m pip install "git+https://github.com/LE0-Lin/AgentConfigScore.git@$ACS_TOOL_REVISION"
      - name: Review declared API-task context
        env:
          BASE_COMMIT: ${{ github.event.pull_request.base.sha }}
        run: >-
          agent-config-score scope diff "$BASE_COMMIT"
          --target src/api/service.py
          --fail-on-lost-directives --fail-on-unknown
```

The recipe pins tool source containing these unreleased commands separately
from the repository being checked. Installing the published v0.24.0 package or
using the rolling `v0` Action does not supply them. Choose task files relevant to
your repository and review each declared context; one context is not
whole-repository coverage. The workflow uses ordinary read-only PR permissions.

The profile inherits its bounded metadata/glob/prose grammar, whole-repository
supported-source preflight, ignore rules and non-atomic filesystem limits.
Targets are logical names whose existence is not checked. No Cursor process,
model API, agent execution, maintainer contact or upload is involved. Try the
[four synthetic examples](../examples/cursor-scope-impact/README.md).
