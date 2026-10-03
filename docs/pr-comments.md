# Post results as one pull request comment

Copy [`examples/pr-comment.yml`](../examples/pr-comment.yml) to
`.github/workflows/agent-config-regression.yml`. Each pull request receives one
AgentConfigScore comment; subsequent runs update it with the score change,
passed/blocked result, finding counts, and a link to the detailed job summary.

The action already produces the detailed report without comments. This optional
workflow grants `pull-requests: write` to publish the compact result. It uses
`pull_request`, cancels older runs for the same PR, and pins the comment action
to a reviewed commit. Do not install multiple copies of this workflow.

## How the comment behaves

- The first completed scan creates a comment. Reruns update the same comment.
- The lookup paginates, so long PR conversations do not hide the existing comment.
- Only a `github-actions[bot]` comment with the dedicated marker is updated.
  User comments containing the marker are left alone.
- Identical content is not written again.
- A blocked regression still gets a comment when the action has produced outputs.
  A cancelled run or scan setup failure does not post a misleading result.
- Malformed or inconsistent numeric outputs fail validation before any API write.
- Failure to post a comment leaves the regression step's outcome unchanged.

## Forks and permissions

The scanner and job summary run for fork PRs too, but the comment step is skipped
because their tokens normally cannot write comments. Repositories that disable
write tokens can use the default read-only setup and job summary instead.

Do not switch this recipe to `pull_request_target` to enable comments on forks.
The recipe checks out the candidate repository, and that event has different
privileges. It would require a separately designed workflow.

The comment script uses validated numeric outputs rather than instruction text,
filenames, suppression reasons, or PR titles. See the
[GitHub script documentation](https://github.com/actions/github-script#passing-inputs-to-the-script)
for why values are passed through environment variables rather than inserted
into JavaScript. Bot-owned comment behavior assumes the standard GitHub.com
`GITHUB_TOKEN`; custom comment identities need their own ownership check.

For the action's output contract, see **Action outputs** in the main README.
