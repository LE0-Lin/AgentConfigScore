# Post AgentConfigScore results as a pull request comment

AgentConfigScore writes its regression report to the GitHub Actions job summary by default. Repositories that want the result directly in the pull request conversation can add a small follow-up step without giving the AgentConfigScore action write permission itself.

This is intentionally opt-in: many repositories prefer read-only CI permissions, and pull requests from forks require extra care around write tokens.

## Copy-ready workflow

```yaml
name: agent-config-regression

on:
  pull_request:

permissions:
  contents: read
  pull-requests: write

jobs:
  regression:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
        with:
          fetch-depth: 0

      - uses: LE0-Lin/AgentConfigScore@v0
        id: acs

      - name: Comment score
        if: always() && steps.acs.outputs.head-score != ''
        env:
          GH_TOKEN: ${{ github.token }}
          PR_NUMBER: ${{ github.event.pull_request.number }}
          BASE_SCORE: ${{ steps.acs.outputs.base-score }}
          HEAD_SCORE: ${{ steps.acs.outputs.head-score }}
          DELTA: ${{ steps.acs.outputs.delta }}
          NEW_FINDINGS: ${{ steps.acs.outputs.new-findings }}
          NEW_ERRORS: ${{ steps.acs.outputs.new-errors }}
          RESOLVED: ${{ steps.acs.outputs.resolved-findings }}
        shell: bash
        run: |
          body=$(cat <<EOF
          ## AgentConfigScore

          **Score:** ${BASE_SCORE} → ${HEAD_SCORE} (${DELTA})

          | New findings | New errors | Resolved |
          |---:|---:|---:|
          | ${NEW_FINDINGS} | ${NEW_ERRORS} | ${RESOLVED} |

          See the AgentConfigScore job summary for the line-by-line report.
          EOF
          )
          gh pr comment "$PR_NUMBER" --body "$body"
```

The regression action exposes its outputs before returning the final pass/fail status, so `if: always()` can still publish the result for a blocked pull request.

## Avoid comment spam

The minimal recipe above creates one comment per workflow run. If your repository reruns CI frequently, prefer updating a bot-owned sticky comment rather than posting repeatedly. Keep that logic in the caller workflow so AgentConfigScore itself remains deterministic, dependency-free, and read-only by default.

## Security notes

- Keep the default AgentConfigScore action read-only unless your repository explicitly wants PR comments.
- Do not switch an untrusted fork workflow to `pull_request_target` merely to obtain a write token; that event has different security semantics and can expose privileged context if used incorrectly.
- The comment uses only numeric AgentConfigScore outputs. The detailed report remains in the job summary, avoiding interpolation of repository-controlled instruction text into a shell command.
- Organization policies can restrict `GITHUB_TOKEN` write permissions. In that case, leave comments disabled and rely on the job summary.

For the action's complete output contract, see the **Action outputs** section in the main README.