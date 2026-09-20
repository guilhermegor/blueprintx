# Is the open-time review ask worth the window? (blueprintx#567)

- [x] Widen the attribution measurement to >= 7 days, paging the comment stream to exhaustion
- [x] Report accepted-review share by trigger source
- [x] Decide: keep `opened`, or reduce `types:` to `[reopened, ready_for_review]`
- [x] Record the decision and the number in `.github/workflows/coderabbit_trigger.yml`'s header

**Completed — kept as a record.** Decision: **keep `opened`.** The reasoning is in the
workflow header; the data and the method that produced it are here, so the next reader can
re-run it rather than re-derive it.

## Why this file is in `docs/backlog/` and not `.specs/`

`.specs/CLAUDE.md` restricts `features/<name>/` to `design.md` and `plan.md` and says in so
many words that anything which does not fit belongs in `docs/backlog/`;
`bin/ci/check_specs_structure.sh` enforces it. A measurement record is neither a design nor a
plan. It also sits beside its own precedent: `coderabbit-incremental-review-362_20260830_172225.md`
is the file #454's `synchronize` paragraph points at. When blueprintx#575 moves `docs/backlog/`
wholesale, this file moves with it.

## Method

Source: `GET /repos/guilhermegor/blueprintx/issues/comments?sort=created&direction=asc&per_page=100&page=N&since=2026-09-06T00:00:00Z`,
paged until a page returned fewer than 100 rows.

- **7 pages, 656 comments**, created `2026-08-26T19:02:42Z` -> `2026-09-20T16:56:03Z`.
  (`since` filters on `updated_at`, so the set is a superset of everything *created* in the
  window; the attribution below is cut at `created_at >= 2026-09-06`.)
- The previous attempt at this measurement reached n=10 over 15 hours because only one page
  resolved and the partial read was consumed as complete. That is the error this paging exists
  to avoid, and the page count above is the evidence it was avoided.

Each comment is classified by author and body:

| class | detection | meaning |
|---|---|---|
| ask, on open | non-bot body contains `@coderabbitai review` | posted by `coderabbit_trigger.yml` |
| ask, tick | non-bot body contains `@coderabbitai full review`, no marker | dev-loop reviewer-slot tick |
| ask, retry | same, plus `<!-- retry-rate-limited-review -->` | `review_retry.yml` |
| accepted | CodeRabbit body contains `✅ Action performed` | `Review finished.` / `Full review finished.` |
| refused | `Review rate limited` / `Review limit reached` / `Rate Limit Exceeded` | the window was closed |
| other | `Action not completed` otherwise | no files, >100 files, head commit changed |

Each CodeRabbit verdict is attributed to the most recent ask **on the same PR** that preceded
it. `other` is reported but excluded from the accept rate: it is a property of the diff, not of
the window.

## Result

**2026-09-06 -> 2026-09-20 (15 days), 244 asks, 243 attributed verdicts**

| trigger | accepted | refused | other | total | accept rate | share of accepted |
|---|---|---|---|---|---|---|
| `@coderabbitai review`, on open | 23 | 81 | 7 | 111 | 20.7% | 26.4% |
| `@coderabbitai full review`, tick | 23 | 26 | 2 | 51 | 45.1% | 26.4% |
| `@coderabbitai full review`, retry | 41 | 38 | 2 | 81 | 50.6% | 47.1% |

**2026-09-13 -> 2026-09-20 (last 7 days), 129 attributed verdicts**

| trigger | accepted | refused | other | total | accept rate | share of accepted |
|---|---|---|---|---|---|---|
| `@coderabbitai review`, on open | 9 | 47 | 4 | 60 | 15.0% | 17.0% |
| `@coderabbitai full review`, tick | 18 | 14 | 2 | 34 | 52.9% | 34.0% |
| `@coderabbitai full review`, retry | 26 | 9 | 0 | 35 | 74.3% | 49.1% |

The issue's n=10 sample had the open-time ask taking 2 of 3 accepted reviews. At n=244 it takes
26%, and the direction of the two aimed sources is the opposite of what the small sample showed.
The small sample was not merely thin — it pointed the wrong way.

**First ask per PR, same window:** 95 PRs were asked at all. The open-time workflow placed the
first ask on **78 of them (82%)**; the tick placed 9, the retry janitor 8. Of those 78, **37**
were subsequently picked up by `review_retry.yml`.

## Decision: keep `opened`

Two numbers, and they point opposite ways. The second one wins.

1. **Against keeping it.** The open-time ask is 111 of 244 asks — 45% of everything spent — and
   returns 26% of the reviews that actually happened. It is the blind bid the issue describes.
2. **For keeping it, and decisive.** A refused ask costs nothing (the issue establishes this,
   and the 81 refusals here corroborate it: they produced no review and consumed no window).
   So the open-time ask's real cost is only its 23 *wins* over 15 days — reviews that did
   happen, on real PRs, merely not the most starved ones. Against that, it is the **enrolment
   step**: first ask on 82% of asked PRs, and `templates/python-common/bin/retry_rate_limited_review.py`
   only adopts a PR whose newest reviewer comment **is** a rate-limit notice. A PR nobody ever
   asked about never produces that notice, so dropping `opened` would hide it from the janitor
   as well as from the tick — and the tick exists only while a Claude session is running.

So the trade on offer was: stop roughly 23 blind wins per fortnight, and in exchange lose
unattended enrolment for 82% of PRs. Declined.

**What the failure mode would have been, had it been dropped** — recorded because the issue
asked for it explicitly and because it is the part a future reader will want: never an
unreviewed merge. The required `Review threads answered` check fails a PR with no submitted
review, so a PR opened while no session runs would simply **stall**, red, until a human noticed
it. Visible, not silent — but unbounded, because nothing on a timer would have been watching it.

## Not done, deliberately

- **`.coderabbit.yaml` was not touched.** `reviews.auto_review.*` is already a no-op here:
  CodeRabbit declines automatic reviews below 10 stars and that threshold has no key in the
  schema. Both that file's header and the workflow's say so.
- **No sleep or backoff was added.** The window is an account-level quota, not
  elapsed-time-since-last-ask; a job that sleeps burns runner minutes and still loses the race.
