# auto_incremental_review is on by default (#362)

Created 2026-08-30. Scope: measure whether incremental (post-open) CodeRabbit
reviews on this repo produce new findings or mostly waste a review slot, then
decide `.coderabbit.yaml`.

## Method

- `rtk gh pr list --state all --search "updated:>=2026-08-23"` → 70 PRs
  (open + merged + closed) touched in the last 7 days.
- For each: `gh api repos/.../issues/<n>/comments` and
  `gh api repos/.../pulls/<n>/reviews`, all authors, full timestamps.
- Built one chronological timeline per PR (comments + reviews merged).
  Classified every `coderabbitai[bot]` event by body content
  (`Actionable comments posted: N`, `Review limit reached` /
  `rate limited`, `Walkthrough`, bare "review command invocation"
  acknowledgements, empty-body `PullRequestReview` objects that only wrap
  grouped inline replies — these are GitHub artifacts, not review passes,
  and were excluded).
- **Trigger attribution**: walked the timeline with a `waiting_for_result`
  flag, set by any human/agent comment containing `@coderabbitai` and
  cleared only by the next *content-bearing* CodeRabbit reply (an
  acknowledgement alone does not clear it, because CodeRabbit's full
  reviews complete asynchronously — spot-checked on PRs #339/#300/#291,
  where the real "Actionable comments posted" review lands 1–5 minutes
  after the ack, not within a fixed window). An event with the flag unset
  is `AUTO_OR_UNPROMPTED` — no explicit request found anywhere earlier in
  that PR's timeline.

## Measured, 2026-08-30

| Event population | Count |
|---|---|
| PRs examined | 70 |
| PR-opening CodeRabbit event (seq 1 per PR) | 70 |
| Events AFTER PR-open (the "incremental" population) | 522 |

Incremental events (522) by outcome:

| Outcome | Count | % of 522 |
|---|---:|---:|
| Rate-limited ("Review limit reached" / "rate limited") | 431 | 82.6% |
| **New finding** (`Actionable comments posted: N`, N≥1) | **41** | **7.9%** |
| Chat-quota rate limit (different mechanism — chat messages, not reviews) | 33 | 6.3% |
| Other / unclassified (e.g. "outside diff" preamble-only replies) | 17 | 3.3% |

Incremental events by trigger attribution:

| Attribution | Count | Rate-limited | New finding | Other |
|---|---:|---:|---:|---:|
| Preceded by an explicit `@coderabbitai review`/`full review` comment | 485 | 405 | 33 | 47 |
| No explicit request found (`AUTO_OR_UNPROMPTED`) | 37 | 26 | 8 | 3 |

## Reading the numbers

- **"Mostly no-ops and rate-limits" is confirmed at the aggregate level**:
  92% of incremental events (481/522) are not a new finding.
- **But the dominant trigger is an explicit comment, not the automatic
  push detector**: 485/522 (93%) of incremental events are attributable to
  a human/agent `@coderabbitai review` comment (this repo's fix-and-request
  loop habit — see #280, dotfiles-dev#170), not to
  `auto_incremental_review` firing on its own. `auto_incremental_review`
  only gates the *automatic* re-review path; it has no effect on
  explicitly-commanded reviews. CodeRabbit's own reply text confirms the
  command exists specifically "when automatic reviews are paused."
- Only 37 events (7%) have no explicit request anywhere earlier in the
  PR's timeline and are the best evidence available for
  `auto_incremental_review` actually firing unprompted — of those, 26 were
  rate-limited and 8 produced a real finding.
- **UNKNOWN, stated plainly**: the GitHub API does not label which
  mechanism (push auto-trigger vs. slash-command) produced a given review,
  so the 37-vs-485 split is inferred from comment/review adjacency, not a
  first-class field. It is the best available signal, not a certainty.

## Decision

- [x] **Set `reviews.auto_review.auto_incremental_review: false`** in the
  new root `.coderabbit.yaml`. Per the issue's own decision rule ("mostly
  no-ops → turn off") and confirmed at 92% non-actionable. The change is
  zero-risk: the PR-open review and explicit `@coderabbitai review`
  requests are both unaffected, so a genuinely-needed re-review after a
  fix is still reachable exactly the way the issue proposes — as an
  explicit, budgeted request.
- [x] **Did not also lower `auto_pause_after_reviewed_commits`** — moot
  once `auto_incremental_review` is off; there is no automatic path left
  for a commit-count pause to bound.
- [x] **Did not ship this config to `templates/*`.** A generated project
  starts with its own (near-zero) PR volume and quota, and has no evidence
  of the explicit-request loop habit that is this repo's actual quota
  driver — inheriting BlueprintX's own tuning would be a guess, not a
  default. Recommendation left in the PR body for a follow-up decision;
  `templates/*` is outside this change's file surface.
- [x] **The bigger lever is NOT this file.** 93% of incremental review
  activity here is the explicit-request habit itself hitting an already-
  exhausted quota (405/485 explicit requests came back rate-limited). That
  is dotfiles-dev#170's territory (the reviewer-slot budgeting step must
  not fire in the same round as a thread-fix push, since that push already
  spends a request) — flagged, not fixed here.

## Completed 2026-08-30 — kept as a record

Every box ticked. `.coderabbit.yaml` written with the measured justification
inline; this file is the permanent record of the method and counts behind
that decision.
