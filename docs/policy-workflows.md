# Repo policy workflows

Scaffolded GitHub repos carry five server-side PR/issue policies in `.github/workflows/`
(blueprintx#604). Local hooks only guard one machine; these run for every contributor.
Offline scaffolds (no GitHub remote) do not receive them.

| Workflow | Rule |
|----------|------|
| `close-linked-issues.yml` | On a merged same-repo PR into the default branch, closes the issues named by the branch (`<type>/<N>-<slug>`) or by `Closes/Fixes/Resolves #N`. |
| `branch-has-issue.yml` | Fails a PR whose head branch carries no issue number (`<type>/<N>-<slug>` or a trailing `-<N>`). `release/`, `dependabot/` and `renovate/` branches are exempt. |
| `pr-title-conventional.yml` | Fails a PR title that is not a Conventional Commit; squash merges use it as the commit subject. |
| `pr-body-template.yml` | Fails a PR body missing a `## ` section of `.github/PULL_REQUEST_TEMPLATE.md`. |
| `pr-self-assign.yml` | Assigns the author when a same-repo PR is opened. |

The checks run `bin/check_pr_policy.sh`, copied into the project (never fetched at run time).
Untrusted branch, title and body text reaches the scripts through `env:` only.

Moving cards to In progress / In review is out of scope: `GITHUB_TOKEN` cannot write a
user-owned Projects v2 board, so that stays in a local hook or behind a PAT secret.
