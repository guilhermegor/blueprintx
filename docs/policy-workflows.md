# Repo policy workflows

Scaffolded GitHub repos carry five server-side PR/issue policies in `.github/workflows/`
(blueprintx#604). Local hooks only guard one machine; these run for every contributor.
Offline scaffolds (no GitHub remote) do not receive them.

| Workflow | Rule |
|----------|------|
| `close-linked-issues.yml` | On a merged same-repo PR into the default branch, closes the issues named by the branch (`<type>/<N>-<slug>`) or by `Closes/Fixes/Resolves #N`. |
| `branch-has-issue.yml` | Assigns the author when a same-repo PR is opened (job `assign`), then fails a PR whose head branch carries no issue number (`<type>/<N>-<slug>`), that has no assignee, or that is linked to no real issue. `release/`, `dependabot/` and `renovate/` branches are exempt from the branch rule. |
| `pr-title-conventional.yml` | Fails a PR title that is not a Conventional Commit; squash merges use it as the commit subject. |
| `pr-body-template.yml` | Fails a PR body missing a `## ` section of `.github/PULL_REQUEST_TEMPLATE.md`. |
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
- The `assign` job skips fork PRs and holds `pull-requests: write`; the `check` job, which `needs: assign`, stays read-only.
- `assign` is idempotent: it runs on any event except `assigned`/`unassigned` while the PR has no assignee, so a cancelled `opened` run cannot leave the author unassigned.
- `check` checks out `base.sha` with `persist-credentials: false`, so the token never reaches PR code. `Branch has issue / check` is not in any shipped `required-checks` list; a repo that required it by hand gets the new rules at once.
- A fork PR is not auto-assigned, so the assignee rule fails it until a maintainer assigns someone; the `assigned` trigger re-runs the check. This is intended.
- The new check names are deliberately absent from each tier's `bin/required-checks.txt`, which
  allows a name only after a real PR has emitted it. Add them once they have reported.
- Offline scaffolds drop `.github/` but keep `close_linked_issues.sh` and `check_pr_policy.sh` in `bin/`, and drop `dependabot_auto_merge.sh` (tracked in #727).

## Assignee and linked issue (blueprintx#937)

`check_pr_policy.sh assignee` fails when `ASSIGNEES` is blank. `check_pr_policy.sh linked-issue` reads
`BRANCH`, `TITLE`, `TRACKER` and `CLOSING_COUNT`; `dependabot/` and `renovate/` branches skip it, since a
dependency bump has no issue behind it. `release/` keeps its branch-rule exemption only.

| `TRACKER` | Passes when |
|-----------|-------------|
| `github` (default) | `CLOSING_COUNT` (GraphQL `closingIssuesReferences`) is above 0, or the branch number resolves to an `OPEN` issue via `gh issue view`. |
| `linear` | A team key such as `ABC-123` appears in the branch or title (case-insensitive; a leading `<user>/` is ignored; acronyms such as `UTF-8`, `SHA-256` and `node-20` are not keys); Linear's GitHub integration links on that key. Use `regex` with your team key for a stricter match. |
| `regex` | `TRACKER_REGEX` matches the branch or title. |

The workflow reads the tracker from the repository variables `PR_TRACKER` and `PR_TRACKER_REGEX`. The
script takes forge and tracker only from the environment, so a GitLab caller (out of scope here) is a new
wrapper, not a rewrite.

Self-assignment lives in the same workflow as the check, as a job the check `needs:`, because a separate `pr-self-assign.yml` raced the check on `opened` and its `GITHUB_TOKEN` assignment never re-triggers workflows. The check reads assignees live from the API and also runs on `assigned`/`unassigned`, so a manual change re-evaluates it.

Bot PRs are skipped by the workflow job (`user.type == 'Bot'`) and so never hit the assignee rule here.
Giving each tier's `dependabot.yml` an `assignees:` entry set to the repo owner at scaffold time is
tracked as a follow-up: it needs the scaffold scripts, which this change does not touch.
