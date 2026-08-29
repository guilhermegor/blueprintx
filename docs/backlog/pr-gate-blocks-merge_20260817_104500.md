# The PR gate needs to BLOCK the merge, not just report

**Created:** 2026-08-17 · **Base:** `main` @ `aaffe2b` · **Issue:** #173
**Origin:** the owner pointed out, looking at the just-merged PR #184: *"there is NEVER a CI
block for unanswered & unresolved-marked conversations... you can't just rely on memory,
lessons, whatever, because they're probabilistic, not deterministic"*. He's right.

---

## Measurement (before)

```text
required_status_checks       : null      ← ZERO required checks
enforce_admins               : false     ← every protection is advice to the owner
required_conversation_resolution : true  ← exists, and was decorative
```

PR #184 merged with **32 of 47 checks passed**. No rule objected, because there was none: the
47 checks run and block nothing. And `required_conversation_resolution: true` protected
nothing at all, because `enforce_admins: false` lets the admin — the only person who merges
in this repo — silently override it.

#184's threads were in fact answered and resolved at the moment of merge (verified via
GraphQL). That's the point, not the defense: **it was luck, not a guarantee.**

## The three layers, and why none of them blocks

| Layer | Covers | Why it wasn't enough |
|---|---|---|
| `Review threads answered` job | missing response | runs, goes red, and **wasn't required** |
| `required_conversation_resolution` | missing resolution | enabled, but **bypassed by `enforce_admins: false`** |
| local hook `pr_merge_threads_guard.sh` | both, on `gh pr merge` | it's local: gone on another machine, in CI, in the GitHub UI |

Three probabilistic layers don't add up to one deterministic one.

## What was blocking making the check required

The objection recorded in `review_threads.yml`'s header was real, but **partial**: resolving a
thread triggers no workflow at all (`pull_request_review_thread` is a webhook, not a trigger),
so a check requiring RESOLUTION would stay red-stale forever.

Except the job **doesn't require resolution** — it runs with
`REVIEW_THREADS_REQUIRE_RESOLVED=0` and asserts only that there was a RESPONSE. And a
response **does trigger** `pull_request_review_comment`. On top of that the job runs `on:
pull_request`, so it reports on every PR from the moment it opens — the property a required
check needs to have so it doesn't lock everything up.

In other words: it was safe to require it at all times. The clean split is

- **response** → the job, required, updates itself;
- **resolution** → native `required_conversation_resolution`, evaluated at the merge button,
  cannot go stale.

Each half stays with whoever can re-evaluate it.

> 🔴 **SUPERSEDED on 2026-08-24 (#196, PR #264). DO NOT follow the split above.**
>
> The job **now requires both halves** — `REVIEW_THREADS_REQUIRE_RESOLVED: "1"`, both in this
> repo's workflow and in the template. The reasoning above is still correct about the
> *trigger* and wrong about the *delegation*: `required_conversation_resolution` **discards an
> `isOutdated` thread**. Measured in #193 — the merge button enabled over a thread with
> `resolved=False outdated=True`, 29 of 29 checks green and the setting confirmed `enabled`.
> A thread goes outdated when the **author's own commit** rewrites the commented lines — that
> is, exactly the state the author can manufacture.
>
> So the half nobody could re-evaluate was also the half nobody was checking. The accepted
> cost: after resolving, the check stays **RED** until someone re-runs the run — which is why
> **#263** stopped being cosmetic (the re-run is the only way a ready PR turns green). See
> `issue-waves_20260823_145527.md`, Wave B section.

🔴 **SUPERSEDED ON 2026-08-24 — #263 was DELIVERED (PR #266, v0.16.6).** The line "the re-run
is the only way a ready PR turns green" **overstates today's cost** and should not be read as
the standing rule. What changed and what didn't:

- **Changed — provided the token has `actions: write`:** OLD failures piled up in the rollup
  no longer require a manual re-run. A run that passes re-runs the same head's stale failures
  by itself (`templates/python-common/bin/rerun_stale_gate_runs.sh`, the `Clear stale failed
  runs` step). Measured live on PR #266 itself: `Re-ran 4 stale failed run(s)`, and the PR
  reached `CLEAN` with **zero** manual re-runs — the first in the wave that needed none.

  ⚠️ **The permission is not an implementation detail, it is the condition behind the line
  above** — and in this repo it is demonstrably load-bearing: measured on 2026-08-24,
  `GET /actions/permissions/workflow` responds `default_workflow_permissions: "read"`. In
  other words, it's the `permissions: actions: write` block **declared in the workflow** that
  enables the cleanup; whoever removes that line thinking it's redundant goes back to the old
  behavior **silently** (the janitor warns and exits 0 on purpose).
  The one case no declaration covers is a **PR from a fork**, where `GITHUB_TOKEN` is
  read-only by definition. There, manual re-runs are still N, not one. So "one click instead
  of N" holds for a PR from the repo itself — this project's single-maintainer case — and
  **not** universally.
- **Did NOT change:** resolving a thread still triggers nothing. If nothing else runs after
  the resolve, **one** manual re-run is still needed. The #216/#180 ceiling is still real;
  what dropped was the SCALAR cost (1 → 5 → 7 depending on the number of answered threads),
  not the ceiling.

In other words: the manual re-run stopped being the only way out and became, in the worst
case, **one** click instead of N.

---

## Execution

### In this repo (applied live)

- [x] `enforce_admins: true` — without it everything else is advice
- [x] `required_status_checks.contexts = ["Review threads answered"]`
- [x] `required_conversation_resolution` confirmed `true`
- [x] rest of the protection preserved on the PUT (linear history, no force-push, no deletions)

### In the template (so duskko is born with this)

- [x] `REQUIRED_CHECKS` stops being empty: gets `"Review threads answered"`
- [x] the comment explains why **this** name isn't a guess (it's the `name:` of the job the
      template itself ships) and why requiring resolution there would lock things up
- [x] the step now **prints the blocking set**; empty became a `warning`, not `info`
- [x] the ruleset already had `required_review_thread_resolution: true` and sends no
      `bypass_actors` (default = no bypass), so that half was already correct there

### Pending

- [x] decide with the owner whether the required set grows beyond the threads check
      (candidates: `Scaffold + lint + test — *`, `Spell check`, `ShellCheck`, `MkDocs build`)
      — **decided and applied.** Measured via the API on 2026-08-22: `main` requires **15**
      contexts, all candidates included, plus `actionlint — workflows (repo + templates)`,
      `Version sync — pyproject vs CLI`, `Validate skeleton.meta integrity`,
      `Shared test copy lists — scaffolds vs python-common` and the two multi-intent jobs.
      ⚠️ `strict` stays `false` (does not require the branch to be up to date before merge)
      and `required_approving_review_count` is **0** — the block comes from the checks, not
      from human approval. `required_conversation_resolution` is `true`.
- [x] prove the block on a real PR before closing #173 — **PROVEN 2026-08-22, with a negative
  control**, after two premature conclusions of mine on the same day.

### The proof of the block (#173) — with both sides

| commit | `Review threads answered` gate | `github-advanced-security` | `mergeStateStatus` |
|---|---|---|---|
| `9e7d1fe` | **fail** (no review) | fail | **BLOCKED** |
| `7efc1e4` | success | **fail** | **CLEAN** |

The second row is the negative control that was missing: with GHAS red and the gate green the
PR reads **CLEAN**, so GHAS **does not block**. In the first row the only difference is the
gate. **That's what held the button.**

⚠️ **Two premature conclusions, both from ONE reading of an asynchronous field:**

1. First I ticked this box reading `BLOCKED` next to the red gate — without enumerating what
   else could be blocking.
2. Then I unticked it, seeing `a1ba4a6` (15/15 green, GHAS red) respond `BLOCKED`, and blamed
   GHAS. Also wrong: `7efc1e4` has the **same** configuration and responds `CLEAN`. The only
   consistent explanation is that the reading on `a1ba4a6` was **stale** — the propagation
   hypothesis I had declared refuted too early, twice.

**The rule left standing, and the one that cost three rounds:** `mergeStateStatus` is
**computed asynchronously**. One isolated reading supports no conclusion — neither positive
nor negative. Re-read after all checks complete, and only conclude once two separate readings
agree. And `BLOCKED` keeps saying *that*, never *why*: a causal conclusion requires the
negative control, not just the observation.

Two side effects logged in the original observation and still valid:

1. Every PR is born red and stays that way until review arrives. That's correct behavior, but
   `Review threads answered` is **never** green the instant the PR opens — anyone looking too
   early reads it as a defect.
2. The message listed `github-actions` among the expected reviewers — the **#218** defect,
   seen in production and not just read in code.

`github-advanced-security` keeps failing on every PR (**#221**) — permanent red noise, with no
title or summary, but it does **not** block the merge.

---

## `github-advanced-security` (#221) — final decision: document, don't silence

> ⚠️ **Read this before reopening an investigation into this check.** If you got here because
> you saw `github-advanced-security` red on a new PR, the answer is already measured below —
> no need to isolate it again.

**Recon on 2026-08-28** (PR #298, commit `3567e0c`), six days after the original measurement
(#173/#219, 2026-08-22): **the same defect, unchanged.**

```text
Creating copilot-sdk session with model: claude-opus-4.6 and clientName: github/code-scanning
Error creating PR review request: SessionModelError: Execution failed:
  CAPIError: 400 The requested model is not supported.
  (Request ID: F018:23A888:53CD34A:5D159FB:6A90E161)
autofind.js version: 0.1.117
```

with, in the same job's environment: `COPILOT_AGENT_MODEL: sweagent-capi:claude-opus-4.6`,
`COPILOT_API_URL: https://api.individual.githubcopilot.com`. `autofind.js` went from `0.1.116`
to `0.1.117` in between — GitHub keeps deploying the agent — and the 400 survives the deploy.
This confirms it isn't a transient failure: the 400 persists across an agent deploy.

⚠️ **The cause is still unconfirmed.** The log only proves that `The requested model is not
supported` survives the `autofind.js` update. Entitlement is a *hypothesis* — `COPILOT_API_URL`
points at `api.individual.githubcopilot.com`, which suggests it, but GitHub's documentation
says Copilot Autofix is available on **public** repositories without a Copilot subscription.
Either the hypothesis is wrong, or evidence linking the error to entitlement is missing. Do
not log it as fact.

The workflow is still **dynamic** (`event=dynamic`, `path=dynamic/agents/github-advanced-security`,
generated by GitHub, absent from `.github/workflows/`) — there is no YAML here to edit, so the
"fix the configuration" option is ruled out again, on the same evidence.

**The "turn it off" option was checked and it isn't available from the CLI:**

```text
GET /repos/guilhermegor/blueprintx                            → no advanced_security field
                                                                  (public repo: GHAS is free and
                                                                  automatic, no toggle here)
GET /repos/guilhermegor/blueprintx  .security_and_analysis     → dependabot, secret_scanning,
                                                                  secret_scanning_push_protection
                                                                  — no Autofix field
GET /repos/guilhermegor/blueprintx/code-scanning/default-setup → the CodeQL config itself, no
                                                                  Autofix field
```

No documented public REST/GraphQL endpoint was found for the "Copilot Autofix" toggle — the
queries above only show that the responses carry no such field. GitHub's documentation
describes UI-level control at the enterprise, organization and repository tiers, without
documenting an equivalent REST/GraphQL operation. As far as could be determined, it lives only
in **Settings → Code security → Copilot Autofix**, on the dashboard, exactly as #221's original
body already pointed out (`needs the panel — none of this comes out of the CLI`). No agent
with only `gh`/API access managed to press that button in the attempts made here. Who can:
an **administrator with the matching permission** — repository, organization, or enterprise —
not just the owner.

⚠️ **Side effects of turning it off, to weigh beforehand:** GitHub **automatically closes**
open Autofix suggestions. Turning it back on **does not restore them** — new suggestions only
appear on new PRs or after a new analysis. Since here the feature has never produced a single
suggestion (every run fails with 400), the cost is zero in this repo; but the rule applies if
used elsewhere.

### Decision: option 3 — document why it stays red

Not "fix the configuration" (impossible — the 400 is on GitHub's side, no YAML here) nor
"turn it off via CLI" (impossible — the toggle only exists on the dashboard). What's within
reach of a PR in this repo is logging the finding so the next red instance doesn't cost
another round of isolation:

- This file is the record. Whoever sees `github-advanced-security` red on a PR finds here: it
  does not block the merge (proven in #173 above), the root cause is on GitHub's side, no
  action is available via CLI.
- The "turn it off" lever **stays recommended** for whenever the owner goes through the
  dashboard — reversible, described in the original #221 — but it's not something this PR can
  execute.
- This is not the same thing as "fixed": the check's color in the GitHub UI doesn't change
  with this PR — it stays red, with no title, no summary. What changes is that it stops
  costing a fresh investigation every time.

**Consequence for closing #221:** `Refs #221`, not `Closes #221` — the task's criterion is the
check's color carrying information again, and the color itself (what the GitHub UI shows)
did not change. What changed is that the information is now a `grep` away instead of a fresh
investigation.
