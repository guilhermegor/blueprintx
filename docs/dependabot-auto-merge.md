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

The workflow uses `pull_request_target` because one trigger then covers Dependabot
opens and pushes with a write token, and the review event runs the same code. It never checks out PR code; the script comes from
the base commit.

## What counts as a Dependabot commit

Commit metadata proves nothing about who pushed: `web-flow` signs every web-editor and API
commit, and the author is a field any write-access user can set. So the rule has two layers:

1. **Who pushed.** On a `pull_request_target` event the sender must be `dependabot[bot]`. On a
   review event, and in the review-thread gate, every `pull_request` workflow run on the head
   commit must have been started by `dependabot[bot]` (REST `actions/runs?head_sha=...`, the
   run's `actor`; a re-run by a human does not change it). A human push, an unreadable
   result, no run, or a truncated list all fail closed. A non-Dependabot synchronize also
   disables auto-merge, and it stays off until Dependabot pushes again.
2. **What was pushed.** Every commit has author `dependabot[bot]`, committer `web-flow` and a
   verified signature (the gate reads GraphQL `signature.isValid` with signer `web-flow`).

A merge commit from the "Update branch" button fails both layers; `@dependabot rebase`
restores the PR.

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

## Behaviours to know

- A human reopen does not re-arm: `reopened` is not a trigger, so the PR waits for the next
  Dependabot push (`@dependabot rebase`) or a qualifying review.
- A human `labeled` or `edited` run on the head commit also counts as "not pushed by
  Dependabot" in the pusher lookup, because the API has no event-action filter. That fails
  closed: the PR needs a review or `@dependabot rebase`.
- A reviewer-bot `COMMENTED` review can arm a major, but arming only queues the merge. The
  required `Review threads answered` check still fails while the ladder's body findings are
  unanswered (blueprintx#630), so nothing merges unread.
- Auto-merge needs "Allow auto-merge" and required status checks on the repository; without
  them `--auto` fails or merges immediately.
