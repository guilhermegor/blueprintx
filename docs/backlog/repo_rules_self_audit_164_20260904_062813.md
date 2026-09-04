# Repo rules self-audit (#164)

Created 2026-09-04. Read-only audit: does `guilhermegor/blueprintx` itself match what
`bin/enable_repo_rules.sh` / `bin/enable_security.sh` (shipped to every generated project)
impose? Their **provisioning path was never run against BlueprintX** (no writes, ever — and
none in this pass either); their read-only `verify` path WAS run here, and is where the numbers
below come from. One drift (`required_approving_review_count: 1`) was already found and
hand-fixed on 2026-08-09 — this issue asks whether more drifted.

⚠️ **Scope note — two different deliverables, only the first two are done here:**
1. measure the divergence between blueprintx's repo config and what the scripts impose — DONE.
2. decide, item by item, what applies to blueprintx vs what's an exception — DONE (below, and as
   comments in the scripts).
3. apply what applies — **NOT done**. Running these scripts (or equivalent `gh api` writes)
   against `guilhermegor/blueprintx` is an outside-in change to the live repo and was explicitly
   out of scope for this pass. Every measurement below is a `gh api` **read**, never a write.
4. decide `REQUIRED_CHECKS` content for a generated project — DONE (kept as-is, see below).

## Method

`gh api repos/guilhermegor/blueprintx/...` reads only, plus `bash templates/python-common/bin/
enable_repo_rules.sh verify` — the script's own read-only guard (blueprintx#307), which needs no
admin rights and never writes.

## Measured divergence

| Item | Script imposes | BlueprintX has (measured 2026-09-04) | Verdict |
|---|---|---|---|
| Mechanism | a named ruleset `pr-quality-gate` (`gh api .../rulesets`) | **zero rulesets** (`[]`) — classic branch protection instead | mechanism mismatch (see exception below) |
| `strict_required_status_checks_policy` / classic `required_status_checks.strict` | `true` (blueprintx#307) | **`false`** | 🔴 real divergence — confirmed independently by `enable_repo_rules.sh verify`, which exits 1 with `strict is NOT true` |
| `required_approving_review_count` | `0` | `0` | in sync (fixed 2026-08-09) |
| `required_review_thread_resolution` / `required_conversation_resolution` | `true` | `true` | in sync |
| `non_fast_forward` / `deletion` (no force-push, no branch deletion) | on | `allow_force_pushes:false`, `allow_deletions:false` | in sync |
| `do-not-merge` label | created by `ensure_optout_label` | **404 — absent** | 🔴 real divergence |
| `allow_auto_merge` / `delete_branch_on_merge` | `true` / `true` | `true` / `true` | in sync |
| CodeQL default setup | `state=configured` | `state=configured` | in sync |
| `copilot_code_review` rule | provisioned via the ruleset | absent (no ruleset exists at all — see mechanism mismatch) | can't assess independently; likely N/A, see exception below |
| Dependabot alerts / security updates / private vuln. reporting (`enable_security.sh`) | all three enabled | all three enabled | in sync — no divergence found in `enable_security.sh`'s territory |
| `REQUIRED_CHECKS` list | template seeds 1 entry, for a **generated** project | blueprintx's own classic protection requires **15** contexts | not comparable — see below |

## Item-by-item: applies to blueprintx vs. exception

- **`strict_required_status_checks_policy` = true — APPLIES, is a real gap.** BlueprintX argued
  for this itself (blueprintx#307: a PR merged with 6 tier checks red only because a dependency
  PR hadn't merged yet). Its own `main` doesn't enforce it. Flagged for a maintainer with
  repo-admin — see "How to apply" below. ⚠️ **NOT via `poe enable_repo_rules`**: that command
  provisions the `pr-quality-gate` ruleset, which is the very second enforcement surface the
  exception two bullets down argues against. Not done here (no writes this pass).
- **`do-not-merge` label — APPLIES.** One `gh label create` call away; not a config-shape
  question, purely an oversight from the script never having been run here.
- **Ruleset vs. classic branch protection — EXCEPTION, not a defect.** BlueprintX's `main` has
  used classic protection since before this script existed (blueprintx#99, 2026-06). Migrating
  to the ruleset mechanism is a real change with its own risk (a stray POST would layer a second,
  1-check-only enforcement surface next to the existing 15-check classic one — GitHub enforces
  the union of both, so nothing breaks, but it's two sources of truth for the same guardrail).
  `enable_repo_rules.sh` already treats this repo as the example of the exception: its own
  `assert_branch_protection_strict()` comment names blueprintx#164 as proof classic protection
  is a legitimate, supported mechanism, not a fallback to be migrated away from. Recommendation:
  fix `strict` (above) on the classic protection blueprintx already has; do not additionally
  provision the ruleset here.
- **`REQUIRED_CHECKS` (15 vs 1) — EXCEPTION, not a defect.** BlueprintX's 15 required contexts
  (`Scaffold + lint + test — <tier>` × 7, `Spell check`, `ShellCheck`, `actionlint`, `MkDocs
  build`, `Version sync`, `Validate skeleton.meta integrity`, `Shared test copy lists`, `Review
  threads answered`) are this repo's *own* CI — the multi-skeleton scaffold-testing pipeline. A
  generated project ships none of those jobs; its CI is `templates/python-common/.github/
  workflows/tests.yaml`'s single matrix job (`Run Automated Tests (<os>, py<version>)`, 15 legs
  from a 3×5 matrix) plus the shared `review_threads.yaml` job. The two lists audit two
  different repos' CI graphs and were never meant to match 1:1.
- **`copilot_code_review` — EXCEPTION, likely N/A.** The script's own header already documents
  that this rule is REST-configured but plan-gated: it sits correctly configured and silently
  inert without a qualifying Copilot plan (Copilot Free does not include code review). Whether
  it's worth provisioning depends on the maintainer's plan, not on this audit — noted, not
  chased further.

## Decision: `REQUIRED_CHECKS` for a generated project — kept at one entry

The seeded value (`templates/python-common/bin/enable_repo_rules.sh`) stays
`REQUIRED_CHECKS=("Review threads answered")`. Not expanded. Reasoning, consistent with the
"measure population before requiring" rule already applied to GitGuardian
(`templates/python-common/.github/workflows/secret_scan.yaml` — excluded because it never
reports on a fork/first run):

- The one seeded entry is correct by construction: it is the literal job `name:` in
  `review_threads.yaml`, a workflow this same template ships, triggered on `pull_request` — so it
  reports on every PR from the moment it opens, the one property a required check must have.
- Every other candidate in a generated project's own `tests.yaml` collapses to a **single**
  check-run name per matrix leg (`Run Automated Tests (<os>, py<version>)`) — adding it would
  require requiring all 15 matrix legs by exact name (they change if the matrix changes), which
  is precisely the "guessed name that drifts" failure the script's own header warns against.
  No fresh scaffold + real PR was run in this pass to capture those exact leg names, so there is
  no population evidence to require any of them yet — the existing comment block in the script
  already says this must come from a **real PR's** check-run list, not be guessed.
- Net: the population bar (blueprintx#164 / GitGuardian precedent) is met for the one entry
  already there and not met for anything else. No script change was needed for this decision —
  it was already the shipped behavior; this audit just re-confirms and records the reasoning.

## Finding: no dry-run mode (the absence IS the deliverable for step 1)

- `enable_repo_rules.sh` has a `verify` subcommand, but it audits **only**
  `strict_required_status_checks_policy` / classic `required_status_checks.strict`. It says
  nothing about review count, thread resolution, non-fast-forward/deletion, the code-scanning
  rule, the copilot rule, merge settings, or the `do-not-merge` label — the other 8 items this
  audit had to check by hand with raw `gh api` reads.
- `enable_security.sh` has **no** read-only mode at all — `main()` always attempts the three
  PUTs (idempotent, but never a pure read).
- Both are non-blocking/idempotent by design (never fail `poe init`), which is the right shape
  for the *apply* path — but it means there was no single command to answer "what would this
  script change" without either reading the source and hand-deriving the `gh api` equivalents
  (what this audit did) or actually writing to the repo. Left as a known gap, not fixed in this
  pass — a full dry-run mode is a second script surface, not a comment-only documentation task,
  and out of scope for a read-only audit.

## What shipped

- `templates/python-common/bin/enable_repo_rules.sh` — comment recording this audit's result
  next to the existing blueprintx#164/#307 references, so a future audit finds the answer
  instead of re-deriving it.
- `templates/python-common/bin/enable_security.sh` — comment recording that the self-audit found
  no divergence in its territory (all three toggles already match).
- This file.

## How to apply (targeted writes only — NOT `poe enable_repo_rules`)

⚠️ **The obvious command is the wrong one here, and this is the whole reason this section
exists.** `poe enable_repo_rules` provisions the `pr-quality-gate` **ruleset**. BlueprintX's
`main` is protected by **classic branch protection** and has ZERO rulesets. Running it would not
migrate one mechanism to the other — it would **add a second, independent enforcement surface on
top of the first**, which is exactly the risk the "Ruleset vs. classic" exception above names.
Two surfaces that disagree fail in the worst way available: the merge button's state stops
matching either config, and neither is obviously wrong on inspection.

So the two real divergences are fixed by writing to the mechanism blueprintx **already has**:

```bash
# 1. strict — PATCH the CLASSIC protection, do not POST a ruleset.
#    Re-send the existing contexts: this endpoint REPLACES required_status_checks, so
#    omitting them silently drops every required check.
gh api -X GET repos/guilhermegor/blueprintx/branches/main/protection/required_status_checks \
  --jq '.contexts'          # read them FIRST, then pass the same list back
gh api -X PATCH repos/guilhermegor/blueprintx/branches/main/protection/required_status_checks \
  -F strict=true -f 'contexts[]=<each context from the read above>'

# 2. do-not-merge label — independent of either mechanism.
gh label create do-not-merge --repo guilhermegor/blueprintx \
  --color B60205 --description "Blocks merge; see CONTRIBUTING"
```

Both are `guilhermegor/blueprintx` writes and stay a maintainer decision — nothing here was run.

## Not done (tracked, not silently dropped)

- Applying the two real divergences (`strict` flag, `do-not-merge` label) to
  `guilhermegor/blueprintx` — needs a maintainer with repo-admin, out of scope for this
  read-only pass. **See "How to apply" for why the obvious command is the wrong one.**
- A real dry-run mode for either script.

- [x] Read-only divergence measured, item-by-item exception written, `REQUIRED_CHECKS` decision
      recorded — kept as a permanent record.
