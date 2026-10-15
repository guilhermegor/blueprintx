# Dependabot auto-merge

Dependabot PRs merge themselves when CI proves them safe. The same policy runs on BlueprintX
and in every generated project, from one implementation:
`templates/common/bin/dependabot_auto_merge.sh` and
`templates/common/.github/workflows/dependabot-auto-merge.yml`. BlueprintX's own workflow runs
that script directly; generated projects get a copy at scaffold time.

## Policy

| Update | Review required | Merges |
|--------|-----------------|--------|
| patch, minor | no | on green, via native squash auto-merge |
| major | yes, on the current head | on green, once reviewed |

A Dependabot diff is a version string and a lockfile, so a review of a patch or minor bump has
nothing to read, and CodeRabbit skips bot PRs. CI builds each template and runs its own lint
and tests, which is the real check. Majors can break a template in ways that need judgement,
so they keep the review.

## How it works

1. `dependabot/fetch-metadata` (pinned by SHA) reports every dependency's `updateType`. A
   grouped PR counts as major if any member is.
2. `dependabot_auto_merge.sh` re-checks that the PR author and every commit are
   `dependabot[bot]`, then arms auto-merge for patch/minor. For a major it arms only when
   someone other than Dependabot reviewed the current head; otherwise it waits. Whenever
   it does not arm (a human commit, an unreviewed major, a rebase that superseded the
   review), it also disables auto-merge, so a PR armed at an earlier head never merges on
   stale approval. A submitted review re-triggers the job (`pull_request_review`), so a
   reviewed major merges on green without a manual re-run.
3. The `Review threads answered` gate (`check_review_threads.py`) skips its "a declared
   reviewer must have reported" check for a PR that is `dependabot` (a `Bot`), whose every
   commit is authored by Dependabot, and whose commit metadata (`update-type:`) is only patch
   or minor. Threads are still checked.

## Fail-closed

Each of these removes the exemption, and the PR needs a review as usual:

- the update type is major, missing or unparsable (decided from metadata, never the title);
- the author is not Dependabot;
- any commit is not Dependabot's, so a human push voids it (`@dependabot rebase` restores it);
- the PR has more than 100 commits.

The workflow uses `pull_request_target` because a Dependabot `pull_request` run has a
read-only token and cannot arm auto-merge. It never checks out PR code; the script comes from
the default branch.

## Who counts as a reviewer

A public repo accepts reviews from any account, so a review counts toward a major only when it
is on the current head, in state APPROVED or COMMENTED, and comes from one of:

- a human whose `author_association` is OWNER, MEMBER or COLLABORATOR;
- a reviewer bot: `user.type` is `Bot` and the exact login is a `posts: threads` entry in
  `.review-bots.yaml` (for example `coderabbitai[bot]` and the reviewer-ladder App).

The roster is read from the PR's base branch through the contents API, never from the PR head,
so a commit on the Dependabot branch cannot add itself to it. A `User` account named like a
roster bot does not count, nor does a `posts: status` member such as `github-actions[bot]`. A
trusted CHANGES_REQUESTED on the head blocks. The job gates on the PR author, never the actor
(on a review event the actor is the reviewer), and arms with `--match-head-commit` so GitHub
refuses if the head moved after the check. The review-thread exemption never counts reviews,
so it needs no such filter.

## Unverified until a real major is reviewed

The review-triggered run is untested against a live Dependabot major. Whether the token of a
`pull_request_review` run may arm auto-merge on a Dependabot PR is not verified; if it cannot,
the job fails visibly and the fallback is re-running it from the Actions tab.

## Tests

`tests/test_dependabot_auto_merge.sh` stubs `gh`; the Dependabot cases in `templates/python-common/tests/unit/test_review_threads_gate.py` cover
the gate. Both pin the should-fail cases: major, non-Dependabot author, human commit, and a
grouped PR with one major.
