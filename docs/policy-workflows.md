# Repo policy workflows

Scaffolded GitHub repos carry five server-side PR/issue policies in `.github/workflows/`
(blueprintx#604). Local hooks only guard one machine; these run for every contributor.
Offline scaffolds (no GitHub remote) do not receive them.

| Workflow | Rule |
|----------|------|
| `close-linked-issues.yml` | On a merged same-repo PR into the default branch, closes the issues named by the branch (`<type>/<N>-<slug>`) or by `Closes/Fixes/Resolves #N`. |
| `branch-has-issue.yml` | Fails a PR whose head branch carries no issue number (`<type>/<N>-<slug>`). `release/`, `dependabot/` and `renovate/` branches are exempt. |
| `pr-title-conventional.yml` | Fails a PR title that is not a Conventional Commit; squash merges use it as the commit subject. |
| `pr-body-template.yml` | Fails a PR body missing a `## ` section of `.github/PULL_REQUEST_TEMPLATE.md`. |
| `pr-self-assign.yml` | Assigns the author when a same-repo PR is opened. |
| `dependabot-auto-merge.yml` | Arms auto-merge for Dependabot patch/minor bumps; majors wait for a review. See [Dependabot auto-merge](dependabot-auto-merge.md). |

The checks run `bin/check_pr_policy.sh`, copied into the project (never fetched at run time).
Untrusted branch, title and body text reaches the scripts through `env:` only.

Moving cards to In progress / In review is out of scope: `GITHUB_TOKEN` cannot write a
user-owned Projects v2 board, so that stays in a local hook or behind a PAT secret.

## Design notes

- The three check workflows run on `pull_request_target`, so the workflow definition, the script and the
  template all come from the base branch and a PR cannot rewrite the check that judges it. They never
  check out PR code: branch, title and body arrive through `env:` from the event only. Bot authors (`user.type == 'Bot'`) are skipped.
- `check_pr_policy.sh` takes `BRANCH`, `TITLE` or `BODY` (plus `TEMPLATE`, default
  `.github/PULL_REQUEST_TEMPLATE.md`) from the environment and exits 0 (pass), 1 (violation) or 2
  (bad usage). Sourcing it defines the functions without running them, which the tests use.
- A trailing `-<N>` in a branch name is not an issue number (`chore/bump-node-20` is a version).
- `pr-self-assign.yml` skips fork PRs (read-only token) and needs only `pull-requests: write`.
- The new check names are deliberately absent from each tier's `bin/required-checks.txt`, which
  allows a name only after a real PR has emitted it. Add them once they have reported.
- Offline scaffolds drop `.github/` but keep the two `bin/` scripts (tracked in #727).
