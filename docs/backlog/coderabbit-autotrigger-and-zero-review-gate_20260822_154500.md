# A PR must not be mergeable without a review (#208)

Created 2026-08-22, from a live observation on PR #215: CodeRabbit did not review it, and
nothing on the PR objected. Two halves that only work together — the gate alone blocks every
PR, the trigger alone is a nicety nobody notices failing.

## Measured first, built second

| PR | roster `reviews` | `reviewThreads` | reality |
|----|------------------|-----------------|---------|
| #204 | 0 | 0 | never reviewed — **merged anyway**, 29/30 checks green |
| #213 | 0 | 0 | never reviewed — merged anyway |
| #209 | 10 | 9 | reviewed after a manual trigger |
| #215 | 1 | 4 | reviewed after an API-posted trigger |

- [x] `reviews` is the discriminator, **not** comments: on #204/#213 the roster posted an
      issue comment (the star-gate refusal notice) while `reviews` was 0. A
      "did the roster say anything?" predicate would have passed both.
- [x] An API comment from a **user token** is `user.type: User`,
      `author_association: OWNER` — indistinguishable from one typed in the browser.
      CodeRabbit replied in **9 seconds** and produced 4 threads. The `github-actions[bot]`
      form (`user.type: Bot`) was measured silently ignored on #210.

## Half A — the trigger

- [x] `.github/workflows/coderabbit_trigger.yml`, on
      `opened / reopened / ready_for_review / synchronize`
- [x] `synchronize` included deliberately: with auto-review off, "reviewed at open, real code
      pushed after" is exactly the hole this closes
- [x] Drafts skipped; `ready_for_review` brings them back
- [x] Posts via `secrets.CODERABBIT_TRIGGER_PAT`, **never** `GITHUB_TOKEN`
- [x] **Fails, never skips, when the PAT is absent** — a `continue-on-error` would recreate
      the exact silent no-op being fixed. Fork PRs land here too, correctly.
- [ ] ⚠️ **Manual step, owner only:** create the PAT (fine-grained, this repo,
      `Pull requests: Read and write`) and
      `gh secret set CODERABBIT_TRIGGER_PAT --repo guilhermegor/blueprintx`.
      Until then the job is red on every PR — which is the honest reading.

## Half B — the gate (#208)

- [x] `find_missing_review_problem` fails a PR where **no roster member submitted a review**
- [x] The message states "the reviewer never ran" and explicitly denies the other reading,
      because the two facts used to print identically
- [x] A reviewer that ran and found nothing passes — the success line now says
      "reported and raised no findings (0 review threads)" instead of
      "All 0 review thread(s) answered"
- [x] Exemption: a roster member's own PR (a bot's dependency bump). A gate nobody can
      satisfy gets bypassed with `--admin`, taking the real blocks with it.
- [x] Login spellings normalised on both sides — the REST/GraphQL `[bot]` mismatch already
      made the thread half of this gate silently green once
- [x] `fetch_threads` → `fetch_pull_request`: author, reviews and threads in ONE call
- [x] `main` re-split (`report_verdict`) to stay under the 60-line gate
- [x] 5 new tests (14 → 19). Neutering the guard fails exactly 2 of them.
- [x] Live negative control: #204 and #213 now exit 1; #209 exits 0.
- [x] Template copy synced (`templates/python-common/bin/`), keeping its two local wordings

## Superseded-rule sweep (wrap-up, 2026-08-22)

The new rule went into the code; the OLD rule kept living in the prose beside it — in tracked
files, which outrank memory next session. Found by grepping for the old wording:

- [x] `bin/ci/check_review_threads.py` **and** the template copy — the module docstring ended
      *"which is why an empty thread list is a pass, not a failure."* Rewritten: an empty list is
      not a THREAD failure, and `find_missing_review_problem` owns the other question.
- [x] `.review-bots.yaml` **and** `templates/python-common/.review-bots.yaml` — same claim, and
      this one **ships into every generated project**, so the stale rule would have travelled.
      Marked `SUPERSEDED 2026-08-22 (#208)` rather than silently deleted.
- [x] The test name `test_a_pr_with_no_threads_passes` — renamed to
      `test_no_threads_is_not_a_THREAD_problem`, because a test NAME is a rule statement too and
      that one asserted the superseded claim.

## Follow-up found during the sweep, deliberately not built

`find_missing_review_problem`'s message lists every roster login as expected —
including `github-actions[bot]`, which is declared `posts: status` and therefore can never
submit a review. The behaviour is right (any roster member satisfies it), but the message names
a reviewer that structurally cannot. Fixing it means `load_roster` exposing the `posts` field,
which changes its signature and its tests — worth doing, not worth folding into this PR.

## The secret's NAME was a defect (2026-08-22, found by it biting)

- [x] Renamed `CODERABBIT_TRIGGER_PAT` → **`GH_PAT_REVIEW_TRIGGER`**. The old name reads as
      "CodeRabbit's PAT" when it means "a **GitHub** PAT that triggers CodeRabbit". Measured
      cost: the first person to set it stored a **CodeRabbit API key** from
      `app.coderabbit.ai/settings/api-keys` — a fair reading of the name — and spent two rounds
      on `401 Bad credentials`. Both products call their credential a token, so the variable
      name is the only thing disambiguating them.
- [x] Not `GITHUB_PAT_…`, however well it reads: Actions reserves the prefix.
      Verified against the API, not recalled: `HTTP 422: Secret names must not start with
      GITHUB_`. `GH_` is the closest legal spelling.
- [x] The workflow's SETUP block now says "**GitHub** PAT … NOT a CodeRabbit API key" and states
      the expected `github_pat_` prefix, so the right artifact is identifiable before storing.
- [x] The shape check that caught this stays: `token class: UNRECOGNISED prefix` turned a mute
      401 into the answer in one run, after two rounds of guessing.

⚠️ **The old secret is still stored under the old name and holds a CodeRabbit key.** Delete it
rather than leaving a dead credential: `gh secret delete CODERABBIT_TRIGGER_PAT`.

## Not done here, deliberately

- **The gate is not yet a required check.** It ships enforcing, but adding it to
  `required_status_checks` before the PAT exists would block every PR on a secret that is
  not there. Sequence: set the secret → confirm one PR auto-triggers → then require it.
- **Two copies of `check_review_threads.py` remain** (repo + template), already drifted in
  comments before this change. That is the shape `check_codespell_sync.sh` exists to police
  and the `--root` treatment #189 gave the function-length gate. Worth its own issue; folding
  it in here would bury the gate change.
- **Template propagation of the trigger workflow.** Every scaffolded repo starts at 0 stars,
  so it has this problem by construction. Related to #129, which owns `.coderabbit.yaml`
  but not the auto-trigger question.
