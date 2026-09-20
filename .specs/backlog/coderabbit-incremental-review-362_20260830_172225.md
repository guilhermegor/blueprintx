# auto_incremental_review is on by default (#362)

Created 2026-08-30. Scope: measure whether incremental (post-open) CodeRabbit
reviews on this repo produce new findings or mostly waste a review slot, then
decide `.coderabbit.yaml`.

## Method

- `gh pr list --state all --limit 200 --search "updated:>=2026-08-23"` → 71 PRs
  (open + merged + closed) touched in the last 7 days.
  ⚠️ **`--limit 200` is load-bearing.** `gh pr list` defaults to 30, so the same
  command without it returns 30 and silently understates the cohort — measured.
- For each: `gh api --paginate repos/.../issues/<n>/comments` and
  `gh api --paginate repos/.../pulls/<n>/reviews`, all authors, full timestamps.
  ⚠️ **`--paginate` is load-bearing too.** One page is 30 items; measured on this
  repo, #279 has 43 comments and #291/#315 have 35, so an unpaginated read drops
  the newest events on exactly the busiest PRs.
- Author filter is `coderabbitai[bot]` (the REST login). `coderabbitai` — the
  GraphQL spelling — matches nothing over REST and yields a silent zero.
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
| PRs examined | 71 |
| PR-opening CodeRabbit event (seq 1 per PR) | 71 |
| Events AFTER PR-open (the "incremental" population) | 773 |

Incremental events (773) by outcome:

| Outcome | Count | % of 773 |
|---|---:|---:|
| Rate-limited ("Review limit reached" / "rate limited") | 538 | 69.6% |
| Empty body (grouped-reply wrappers) | 116 | 15.0% |
| Other / unclassified | 77 | 10.0% |
| **New finding** (`Actionable comments posted: N`, N≥1) | **42** | **5.4%** |

⚠️ **These counts replace a truncated first pass** (70 PRs / 522 events / 41
findings at 7.9%). The re-run with `--limit 200` and `--paginate` found 251 more
events and **one** more finding. The truncation was therefore biased *toward*
the conclusion's opposite: it discarded almost pure waste, so the corrected
actionable rate falls from 7.9% to **5.4%**. The conclusion survived the
correction — but it was not entitled to, and the first numbers should not be
cited.

Incremental events by trigger attribution:

| Attribution | Count | Rate-limited | New finding | Other |
|---|---:|---:|---:|---:|
| Preceded by an explicit `@coderabbitai review`/`full review` comment | 485 | 405 | 33 | 47 |
| No explicit request found (`AUTO_OR_UNPROMPTED`) | 37 | 26 | 8 | 3 |

## Reading the numbers

- **"Mostly no-ops and rate-limits" is confirmed at the aggregate level**:
  94.6% of incremental events (731/773) are not a new finding.
- **But the dominant trigger is an explicit comment, not the automatic
  push detector**: 485/522 (93%) of incremental events are attributable to
  an explicit human/agent review-request comment (this repo's fix-and-request
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
  requests are both unaffected. ⚠️ **Not "zero-risk", and the earlier draft
  said so wrongly**: 8 of the 37 no-explicit-request events did produce a real
  finding, and GitHub does not label which mechanism fired, so those are
  *inferred* push-triggered, not confirmed. Disabling the automatic path may
  lose findings of that kind wherever the path is actually live.
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

## Correction, 2026-08-30 — the premise was wrong, the measurement was truncated

Three defects found after the first pass. All were confirmed by measurement, not
argued; the numbers above have been replaced accordingly.

### 1. 🔴 The setting this file recommends is INERT on this repo

The issue that commissioned this work (#362) asserted that
`reviews.auto_review.auto_incremental_review` was the quota vector. Nobody checked
whether CodeRabbit's automatic path runs here. It does not:
`.github/workflows/coderabbit_trigger.yml` lines 5-13 already recorded that
CodeRabbit declines automatic reviews below 10 stars, that the threshold is not
configurable from `.coderabbit.yaml`, and that this repo has 0 stars. Verified:
`stars=0`.

The real consumer is that same workflow, firing on `synchronize` — every push to
an open PR — and posting an **explicit** request via PAT, which is honoured
regardless of auto-review config (line 16 of that file states this; it is the
whole reason the PAT design exists).

Timeline for the incident that prompted #362: trigger run at **15:51**,
rate-limit notice on #357 at **15:52:05Z**.

⚠️ This does not invalidate the measurement — it relocates the remedy. The waste
is real and now better quantified; the file that fixes it is the workflow.

### 2. The documented method truncated, in both calls

`gh pr list` caps at 30 without `--limit`; `gh api` returns one page without
`--paginate`. As written, the method was not reproducible: running it verbatim
returns 30 PRs, not 70. Re-run with both flags, the population is 71 PRs and 773
incremental events — **+251 events, +43%**.

🎯 The correction is worth stating precisely because of how it landed: the extra
251 events contained **one** additional finding. A truncated sample that drops
almost only waste moves the headline rate in the *favourable* direction, so the
first pass was less flattering to its own conclusion than the truth. That is luck,
not method — the same truncation on a different distribution would have inverted
the answer, and nothing in the run would have looked different.

### 3. The attribution split is more approximate than stated

The `waiting_for_result` flag was set by any comment mentioning the reviewer, while
the attribution table counts only `review` / `full review` commands. A non-review
mention therefore marks the following event as explicitly-triggered and inflates
the 485 side of the 485/37 split.

⚠️ **This has NOT been re-measured.** The re-run above recomputed outcomes only, not
attribution. The 485/37 figures are carried forward unchanged and should be read as
an upper bound on the explicit share, with the caveat the original text already
stated: GitHub exposes no field naming the trigger.

### What still needs doing

- [ ] The lever is `coderabbit_trigger.yml`'s `synchronize`, and it is a real trade:
      lines 46-48 explain that removing it reopens the hole through which #204 and
      #213 merged unreviewed. Candidate middle ground — re-request only when the push
      changed reviewable code, or only when threads were resolved since the last
      review.
- [ ] ⚠️ Measure that filter before writing it: of the 773 events, how many followed
      a push touching only `docs/`, `docs/backlog/`, or a thread reply? That number
      decides whether the filter pays.
