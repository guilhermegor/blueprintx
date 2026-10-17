# Decision records

Resolves blueprintx#239. This page is the destination for **decision-record**
comments — the `SUPERSEDED …` blocks that narrate what a nearby line of code
*used to* say and why that reasoning was replaced — split out from **guidance**
comments, which explain what a future editor must not break.

The test (from blueprintx#239): a comment earns its inline place if removing it
would let someone make a *wrong edit to this line*. If removing it only loses
*history*, it belongs here (or the ledger, the issue, the commit message —
whichever already holds it), not inline. The rule is stated for future comments
in `templates/python-common/bin/CLAUDE.md` ("Decision records move to docs, not
a changelog inside the comment").

⚠️ **Not every long or dated comment qualifies.** A measurement that is *why the
code is shaped the way it is today* (no superseded claim, nothing rejected)
stays inline — moving it would turn a justified constant into a magic one. Only
blocks marked `SUPERSEDED` — a changelog entry inside the file — move here.

## `.review-bots.yaml` — zero threads is not a pass (#208)

Applies to `.review-bots.yaml` (root) and `templates/python-common/.review-bots.yaml`
(identical roster comment in both). `.review-bots.yaml` (root, this repo's own data,
never shipped) now points back to this entry. `templates/python-common/.review-bots.yaml`
is copied verbatim into every generated project, so its pointer names the blueprintx
issue directly (`blueprintx#208`) rather than a doc path that would not exist in the
generated repo.

> ⚠️ SUPERSEDED 2026-08-22 (#208). This block used to end "…is a pass here rather than a
> failure", and that half was wrong. Zero threads is ALSO what you get when no reviewer ever
> ran — opposite facts, one number — and the gate reported the second as success: PRs #204
> and #213 merged unreviewed with every check green. Zero threads is now judged against a
> SUBMITTED REVIEW, not against silence. A reviewer that ran and found nothing still passes;
> one that never ran fails.

## `review_threads.yaml` — a required check that reports is safe to require (#173)

Applies to `templates/python-common/.github/workflows/review_threads.yaml` — shipped
into every generated project, so its pointer names `blueprintx#173` directly rather
than a doc path meaningless outside this repo. The live file keeps the load-bearing
half (why the job is safe as a required check and why `bin/enable_repo_rules.sh`
seeds `REQUIRED_CHECKS` with its name) inline; the changelog half moves here.

> ⚠️ SUPERSEDED 2026-08-17 (blueprintx#173). This block used to conclude "that is why this must
> NOT be a required check". That conclusion was WRONG, and it was load-bearing: while it stood,
> `REQUIRED_CHECKS` in bin/enable_repo_rules.sh shipped EMPTY, so a generated project ran its CI
> and blocked nothing. Measured upstream: a PR merged with 32 of 47 checks passed.

**Not yet applied** to `.github/workflows/review_threads.yml` (root) — that file
carries the same block (dated text: "SUPERSEDED 2026-08-17 (#173, PR #185)") plus
two more below, and is held by PRs #491/#492 as of this writing. Follow-up once
those land.

## `review_threads.yaml` — the resolve half must also catch outdated threads (#196)

Applies to `templates/python-common/.github/workflows/review_threads.yaml`. The
"split as it stood" bullet list a few lines below the live comment already states
the current three-layer split in full, so the narrative here is pure changelog.

> ⚠️ SUPERSEDED 2026-08-24 (blueprintx#196). `REVIEW_THREADS_REQUIRE_RESOLVED` IS NOW `1`.
>
> The split below handed the RESOLVE half to the ruleset's `required_review_thread_resolution`
> (`required_conversation_resolution` on classic branch protection) on the reasoning that a
> merge-time setting cannot go stale. True — and it does not check what it was given: GitHub
> DROPS AN OUTDATED THREAD from the blocking set. Measured upstream: the merge button was ENABLED
> over a thread reading `resolved=False outdated=True`, with 29 of 29 checks green and the
> setting confirmed `enabled`. A thread outdates when the author's own commit rewrites the lines
> it points at, so the reachable sequence is: reply thinly, rewrite those lines, merge. The half
> nobody could re-evaluate was also the half nobody was checking.

**Not yet applied** to `.github/workflows/review_threads.yml` (root, held by
#491/#492), `templates/python-common/bin/enable_repo_rules.sh` (the same #196
story, told from the ruleset side — held by the #129 dispatch claim), and
`templates/common/bin/check_review_threads.py` (held by PR #424). Follow-up
once those land.

## `review_threads.yaml` — no `concurrency:` block, ever (#216)

Applies to `templates/python-common/.github/workflows/review_threads.yaml`. The
full reasoning is already restated in the "NO `concurrency:` BLOCK, DELIBERATELY"
comment further down the same file — this block was a preview of that one,
so nothing but the changelog framing is lost by trimming it.

> ⚠️ SUPERSEDED 2026-08-22 (#216). This block used to say `cancel-in-progress` must stay
> **false** below because a cancelled run publishes a `cancelled` conclusion. There is no
> concurrency block at all now, and the reason is worse than that: see the note above `jobs:`.
> `false` does not stop a QUEUED run being cancelled by the next one, and a run cancelled before
> it starts publishes NOTHING — leaving the required context `Expected — Waiting for status to
> be reported`, which no re-run clears.
> Closing this properly inside Actions needs a webhook receiver or GitHub App dispatching a
> `repository_dispatch` on `resolved`; not worth a always-on listener for this repo.

**Not yet applied** to `.github/workflows/review_threads.yml` (root) — held by
PRs #491/#492. Follow-up once those land.

## `.greptile/` — Greptile reviews only when asked (#737)

Every scaffold ships `.greptile/config.json` (from `templates/common/`) with
`"autoReview": []`, plus a per-skeleton `rules.md` and a `files.json` pointing at the
project's `AGENTS.md` or `CLAUDE.md`. The reference default is `["open"]`, which reviews
every PR on open and spends the monthly credit allowance while another reviewer is up.
An empty array means never automatic; the review ladder asks for one explicitly. Do not use
the trigger-label route, which counts as an `open` event and would need `"open"` back.
`greptile-apps[bot]` posts inline review threads, so it is listed in every
`.review-bots.yaml` roster.

## The comment-budget gate and its data files (`templates/python-common/bin`)

`check_comment_budget.py`, `comment_budget_allowlist.txt` and `required-checks.txt` carry no
comments. The module docstring of the gate is the contract; this section records the reasoning
that lived beside the constants and the data.

### `check_comment_budget.py`

- **`INT_MAX_RUN = 85`** is just above the worst block measured on the tree (80 lines), so the
  tree had zero run-length violations when the gate shipped and #304 is what tightens it, not
  the gate. The ratchet, not this ceiling, is the live constraint.
- **The structural-line limit (2)** is not a number to tune: a shebang or PEP 263 coding cookie
  only ever sits on line 1 or 2. A decorative banner is exactly rule, title, rule: three lines.
- **`.py` is deliberately absent from the `#`-suffix tuple**: its blocks come from `tokenize`,
  since a `#` inside a string literal is not a comment and only the tokenizer knows. But
  `marker_for` must still recognise `.py` explicitly, or `file_problems` short-circuits on its
  `not str_marker` guard before the `.py` branch and every Python file goes unchecked while
  `audit_paths` reports it "checked" (#466; measured 228 of 499 files "checked", 0 findings,
  discovery non-zero and looking like coverage). `Makefile` (no suffix) and `.mk` are matched by
  name in `audit_paths` and `marker_for`; the issue's own table missed `Makefile` for this reason.
- **`//` file types.** `/* */` block comments are a known ceiling, not a gap: every measured
  violation in the issue's table is a line-comment block, and a second comment grammar for zero
  measured evidence is the unrequested generality this repo argues against.
- **The skip list** mirrors `check_function_length.py`, `.claude` included: `--root` is
  overridable to the real repo root, which commonly sits under a `.claude/worktrees/<agent>/`
  copy of itself.
- **A decorative banner** is a comment whose stripped content is only rule punctuation
  (`# -------`).
- **The test-section banner exemption.** `tests/CLAUDE.md` used to mandate a banner triple
  (dash rule, section name, dash rule) in every test module. The rule line was measured (#466) to
  occur nowhere else in the tree. It was matched structurally in `banner_findings` and not through
  the pragma allowlist, because a pragma breaks a run (`line_breaks_run`): listing the string there
  would let one dash line split an oversized block into two under-ceiling halves (#479;
  reproduced: 44 lines, one dash line, 44 lines passed clean). The two rule lines still counted
  toward the block's length, and only the banner finding was suppressed, never the run. It was
  scoped to Python test modules (`is_test_module`); the same triple in production code, a
  `Makefile`, shell or `.ts` is a plain decorative banner. Once the convention is removed from
  `tests/CLAUDE.md` and the suite (slice 8 of #304), the exemption has no remaining purpose and
  is deleted in a follow-up, with a should-fail test that a banner in a test module is a finding.
- **A bare `# comment-budget-ok:`** with no reason and no trailing newline leaves
  `.splitlines()` on the tail empty, not `[""]`; indexing `[0]` crashed the first draft instead of
  failing the exemption, which is what a bare marker must do.
- **`--root <dir>`** is a flag plus its value, so argv must hold at least two entries. Zero
  discovered files in audit mode is a failure, not a pass, matching every sibling gate.

### `comment_budget_allowlist.txt`

- **Format.** One substring per line. A comment line that starts with an entry is
  machine-read configuration in comment syntax, not prose being budgeted: it never counts toward
  a run, is never flagged as a banner and is never stripped, and it breaks a run instead of
  extending it (#303). A leading `~` means "contains", for generated-file banners, matched only
  in a file's first lines. Lines starting with `#` are ignored, as are blank lines.
- **Anticipatory, not a census.** Add every pragma form the toolchain in `templates/python-common/`
  can emit, even with zero occurrences today: `codespell:ignore` has no inline use (codespell is
  configured through `.codespellrc`) and belongs anyway, because the first person who legitimately
  needs one must not be the one who finds out the gate has never seen it.
- **The groups**, in file order: ruff, pyright, mypy, pytest/coverage, shellcheck, codespell, this
  repo's own gates (`*-ok:` markers, `pairing:internal`, `pipeline-mode:`, `offline-mode:`,
  `layer-policy`, `gate-change-ok:`), deptry (`per_rule_ignores` and `DEP00N` codes), hadolint and
  Dockerfile parser directives, markdownlint, yamllint, sqlfluff, secrets scanners, formatters,
  the TypeScript and JavaScript toolchain, pylint, generic "do not analyze" markers, dependency
  bots, and ponytail. The last group is structural exemptions (#303): SPDX headers and
  generated-file banners are not the essay or decorative-banner defect the gate polices.
- **The test-section banner is not listed here.** Every entry is a pragma, and a pragma breaks
  the current run. That is right for a QA suppression, but a "banner is a pragma" entry lets one
  dash line split an oversized block into two under-ceiling halves (reproduced as above).
  The exemption was structural in `check_comment_budget.py` for that reason; do not re-add the
  string here.

### `required-checks.txt`

- It lists the status-check names `enable_repo_rules.sh` makes merge-blocking on the default
  branch, one per line, verbatim as GitHub reports them; blank lines and `#` comments are ignored.
- Add a name only after confirming a real PR emits it
  (`gh api repos/:owner/:repo/commits/<pr-head-sha>/check-runs --jq '.check_runs[].name' | sort -u`).
  A name nothing emits blocks every PR forever, since GitHub cannot tell "has not reported yet"
  from "will never report". Deleting a line is always safe; adding an unverified one is not.
- `Review threads answered` is the `review_threads.yaml` job: `on: pull_request` with no filter,
  so it reports from the moment a PR opens, and it fails both when a thread is unanswered and when
  no reviewer ran at all.
- `Classify and gate this PR` is the `pr-gate.yaml` job: `on: pull_request` with
  `types: [opened, synchronize, reopened, labeled, unlabeled]`, and its job-level
  `if: github.event_name == 'pull_request'` is true for every one of those. Without this line the
  gate classifies and fails while nothing stops the merge (#564).

## Root workflows: why each is shaped as it is

These records explain the GitHub Actions workflows under `.github/workflows/` in this
repository. They were moved out of the workflow files, which now carry no prose.

### `coderabbit_trigger.yml` — a user PAT asks for the review

- **Why the workflow exists.** CodeRabbit declines automatic reviews on a repository with
  fewer than 10 stars, and the threshold is not configurable from `.coderabbit.yaml`. The
  consequence was PRs #204 and #213 merging with every check green and no review.
- **Why a PAT and not `GITHUB_TOKEN`.** CodeRabbit ignores bot-authored comments. A comment
  posted with `GITHUB_TOKEN` is authored by `github-actions[bot]` and was dropped silently
  (measured on #210: no reply in 5 minutes). A comment from a user PAT replied in 9 seconds
  (#215). Do not simplify this.
- **The secret is `GH_PAT_REVIEW_TRIGGER`.** The earlier name `CODERABBIT_TRIGGER_PAT` read as a
  CodeRabbit key and cost two rounds of `401 Bad credentials`. Actions reserves the
  `GITHUB_` prefix (`HTTP 422`), so `GH_` is the closest legal spelling. Setup: a fine-grained
  GitHub PAT for this repository with `Pull requests: Read and write`, then
  `gh secret set GH_PAT_REVIEW_TRIGGER --repo <owner>/<repo>`.
- **Fail, never skip, when the PAT is absent.** A skip would reproduce the original defect:
  no review and nothing says so. A fork PR gets no secrets and lands in the same failure,
  correctly.
- **The shape check.** A bare `401` cannot tell a wrong token from a token stored wrong
  (`gh secret set … < file` keeps the trailing newline). The step reports only the token
  class and booleans, never a value, a substring or its length, because the logs are public
  and a substring of a masked secret is not masked.
- **A 403 is a different failure.** It is GitHub's API rate limit for the PAT's user, not
  CodeRabbit's review quota, and clears by itself; it must not read as a bad token. Match on
  `rate limit` alone: the secondary limit's wording ("You have exceeded a secondary rate
  limit", 403 or 429) does not contain the primary's phrase.
- **Triggers.** `synchronize` was dropped in #454: only 5.4% of 773 post-open events produced
  a finding and 69.6% were rate-limit notices, and the required "Review threads answered"
  check already closes the unreviewed-merge hole. `opened` was kept in #567: asks on open are
  45% of all spent but win 26% of reviews, yet they enrol the PR for
  `retry_rate_limited_review.py`, which only adopts a PR whose newest reviewer comment is a
  rate-limit notice. Dropping it would leave a PR opened with no session running stalled.
  Drafts are skipped; `ready_for_review` brings them back.
- **Concurrency may cancel here.** Several pushes need one trigger, and this workflow publishes
  no verdict anyone waits on, unlike `review_threads.yml`.

### `review_retry.yml` — retry a rate-limited review on a timer

- It does not relax the gate. Of 112 PRs, 19 hit a rate limit and 18 were reviewed in the end,
  so a rate limit is a delay and the asking is automated. The 19th (#157) merged with no
  review while a notice stood, which is the hole the gate exists to close.
- A schedule is the only shape that works: nothing fires while a PR waits. Measured windows
  are 10 to 25 minutes, so `*/10` clears most on the first tick after the window.
- It needs the user PAT for the same reason as the trigger. The script reads back the
  comment's author type and warns if it posted as a Bot.
- It asks at most one PR per run, oldest first (#280), which matches the shared account's
  roughly one review per hour.
- It has no secret-shape preflight: with a missing PAT the gate still blocks the PR visibly,
  and a job failing every 10 minutes would be noise.
- Its concurrency group has `cancel-in-progress: false` so a queued run waits and re-reads the
  comments. That does not contradict the no-concurrency rule below: it is a janitor that
  publishes no required check.

### `review_threads.yml` — triggers, concurrency and the stale-run cleanup

- **Triggers are the point.** Under `pull_request` the verdict was computed at push time and
  went stale when a review landed (PR #180 merged with two unanswered threads).
  `pull_request_review` and `pull_request_review_comment` re-run it. `pull_request_review_thread`
  is a webhook event, not a workflow trigger; adding it makes GitHub reject the whole file
  silently (#156), and `bin/ci/check_actions.sh` now catches that class.
- **`issue_comment` is load-bearing.** A clean CodeRabbit review is a plain issue comment, so
  without this trigger the gate stays frozen on its push-time failure (measured on #342: the
  gate was wrong two seconds after the review finished). The job skips plain issues, and reads
  the PR number from `issue.number` on that event.
- **Resolution cannot re-trigger it.** Resolving a thread emits no workflow trigger, so after
  a resolve the run must be re-run once. The job asserts both halves (reply and resolve,
  `REVIEW_THREADS_REQUIRE_RESOLVED=1`) since #196; the earlier split gave the resolve half to
  `required_conversation_resolution`, which drops an outdated thread from the blocking set
  (#193: merge enabled, thread unresolved and outdated, 29 of 29 checks green).
- **It is safe to require.** The earlier note that it must not be a required check was wrong
  and left `required_status_checks` empty, so a PR merged with 32 of 47 checks passing (#173 and
  PR 185).
- **No `concurrency:` block, deliberately.** With `cancel-in-progress: false` only one run
  may sit pending, so each queued run cancels the waiting one (10 runs in 25 seconds on #216).
  A run cancelled while queued publishes no check run, leaving the required context at
  `Expected — Waiting for status to be reported`, which nothing clears.
- **The stale-run cleanup (#263).** Each trigger opens a new check run and branch protection
  reads the aggregate, so a correct push-time failure keeps the PR blocked behind any number
  of later passes (5 on #264, 7 on #265). The `Clear stale failed runs` step re-runs those
  failures. `if: success()` is the loop guard. On `issue_comment` the head SHA must be fetched
  because the event has no `pull_request` object, and an unresolved head fails loudly (#350).
- **Closing the ceiling properly** would need a webhook receiver or a GitHub App dispatching
  `repository_dispatch` on `resolved`. That was rejected as not worth an always-on listener
  for this repository.
- **Its own workflow.** It is kept out of `scaffold_checks.yml` so a review comment does not
  re-run the 29-job scaffold matrix: one job, a few seconds, as often as needed.
- **A finding takes both halves:** reply with what changed and why, then resolve. A bot
  resolves its own threads on seeing the fix, so `isResolved` records the reviewer's
  satisfaction, never the author's reasoning.

### Other workflows

- **`behind_base_gate_report.yml` (#368).** A PR runs every gate from its own checkout, so a
  branch behind `main` can fail or wrongly pass on an old gate. `gh pr update-branch` moves
  the head commit and can supersede a clean review, so the workflow only reports. Its
  schedule is coarse: a `*/10` schedule fired 6 times in 21 hours on this repository.
- **`pr-reconcile.yaml` (#255).** A PR merged by native auto-merge armed with `github.token`
  leaves the linked issue open and the branch undeleted, while a manual merge of the same PR
  closes it. The `pull_request: [closed]` path is an optimisation; the `schedule` path is the
  backstop and the fix, because scheduled events are exempt from the "no new workflow runs"
  suppression. It calls `templates/python-common/bin/pr_reconcile.sh`, the same script a
  generated project calls at `bin/pr_reconcile.sh`.
- **`issue_scope.yml`.** Its own workflow so an issue edit re-runs one job instead of the
  scaffold matrix. It listens to `issues` events because an edit changes the declaration the
  gate judges against, and checks out the base commit, never the merge ref, so a PR cannot
  rewrite `check_issue_scope.py` and judge itself. The only writing job posts a commit status
  on each affected PR head, since an `issues`-triggered job belongs to no PR's check suite.
- **`pr_template.yml`.** Separate because `edited` must re-run it and would otherwise re-run
  every scaffold check on a body edit. It reads the body live from the API, since a re-run
  replays the original event payload.
- **`release.yml`.** The version input is free text and is validated before `git tag`, the
  irreversible step, so a bad value is a no-op instead of a pushed tag with no artifacts.
  `release_snap.yml` fails before its 30-minute build when the credential is absent, because
  an `exit 0` there let v0.16.67 to v0.16.70 report green while nothing reached the store
  (#669). Every package job stamps the release version into the fallback literal of
  `blueprintx --version`, since packaged installs have no `.git`.
- **`verify_branch_protection.yml` (#307).** Guards the `strict` setting, which anyone with
  admin rights can flip with no red check. `GITHUB_TOKEN` cannot read branch protection
  (`administration` is not a grantable scope), so it reuses `GH_PAT_REVIEW_TRIGGER`. It runs
  on push to main, weekly and on dispatch, not on `pull_request`, because it checks a
  repository setting and is not a required check. It fails, never skips, without the PAT.
- **`docs.yml`.** Checks out full history so `cz changelog` sees the tags, and regenerates
  `CHANGELOG.md` fresh on every docs build; it is never committed back.
- **`secret_scan.yml`.** Scans full history. A pinned version fixes what is asked for, never
  what arrives, so the download is SHA-256 verified before extraction, as `lint-actions` does
  for actionlint. A graceful skip is right on a contributor's machine and a placebo in CI, so
  `GITLEAKS_REQUIRED=1` turns a missing install into a failure.

### `scaffold_checks.yml` — notes per job

- **No setup step** for the stdlib-only gates (function length, complexity of `bin/`, comment
  budget, test copy lists, sed portability, git remote guard, scaffold libs): a missing tool
  cannot make a gate report its own blindness as OK, so there is no `*_REQUIRED` flag. The
  complexity job on `templates/python-common` needs ruff, because C901 is the metric, and
  hard-fails when it cannot be resolved.
- **Complexity needs a second invocation (#271)**, scoped to `templates/python-common`, whose
  `src/` and `tests/` the top-level directory lookup cannot see. Function length is not
  duplicated: its discovery already walks the whole root (measured by planting a 66-line
  function there).
- **Sed portability.** GNU `sed -i` takes no argument and BSD requires one, so a bare
  `sed -i` aborts a scaffold on macOS. `sed_inplace()` in `bin/lib/common.sh` is the
  replacement.
- **Test copy lists.** A shared test no scaffold copies is committed and never run in any
  generated project. Its first run found `test_startup_fragility_order.py` absent from all
  five tiers.
- **actionlint.** yamllint asks whether the YAML is valid, actionlint whether GitHub will run
  it, and a workflow GitHub refuses produces no red check. The template workflows are in
  scope because they never execute here. Its tarball is SHA-256 checked for the reason above.
- **GitGuardian is not a required check (#155).** Its population is unmeasured. GitHub gives a
  Dependabot-triggered run a separate secret store holding none, so the key resolves to an
  empty string and `ggshield` exits 3 (#457, PR #400). The job is skipped on the PR author
  (`github.event.pull_request.user.login`, never `github.actor`) when that author is
  Dependabot. This is not a silent pass: `gitleaks` scans the same range unconditionally. The
  fix is `gh secret set GITGUARDIAN_API_KEY --app dependabot --repo <owner>/<repo>`. The
  probe is `gh api repos/<o>/<r>/dependabot/secrets --jq .total_count`, which returned 0, and
  until that secret exists a Dependabot PR trips the job on every run (the log shows
  `GITGUARDIAN_API_KEY:` blank and `Error: Invalid GitGuardian API key.`).
- **ggshield push range.** In ggshield 1.54.0 the previous-commit variable is
  `GITHUB_PUSH_BASE_SHA`, which must carry `github.event.before`; `GITHUB_PUSH_BEFORE_SHA`
  and `GITHUB_PULL_BASE_SHA` appear nowhere in its source, so setting them protects nothing.
  Without a usable previous commit it scans only `GITHUB_SHA~1`, one commit of a
  five-commit push, with exit 0. A branch-creating push (before is forty zeroes) and a manual
  dispatch run a separate full-repository scan in a separately named step, which is the
  correct range for a freshly scaffolded project's first push.
  `GITHUB_DEFAULT_BRANCH` is deliberately left unset, so do not re-add it as protection:
  with a real previous commit its fallback is unreachable, and on a branch-creating push
  its fallback is a bare ref (`main..<sha>`, no `origin/` prefix, because the remote prefix
  is applied only on the pull_request path). A detached checkout has no local `main`, so
  that resolves to nothing and lands back on `GITHUB_SHA~1`. Prefixing it with `origin/`
  does not help either: on the push that creates the branch `origin/main` already equals
  `HEAD`, so the range is empty. The pull_request path needs no variable, because ggshield
  reads `GITHUB_BASE_REF`, which Actions already sets.
- **Scaffold matrix.** `dry-run-smoke` and `scaffold-lint-test` are CI-only (#384): a
  `skeleton.meta` change would trigger one hook, never all six skeletons. `envsubst` is
  installed only when missing, because the unguarded `apt-get` hung two jobs for 6 hours
  (#192). `MULTI_PIPELINE_OPTIN=true` forces the MVC multi-intent prompt to yes. The
  storage opt-in job answers that prompt through the named-key spec on every tier that
  offers it (api-service-native-db uses the DDD key map, #668), because the plain scaffold
  never linted files that ship only on an opt-in (#650).
- **Codespell sync.** The vocabulary this repository learns must reach the copy that ships
  into every scaffold; the two lists drifted in both directions and the stale side was the
  template.
- **Pairing gate.** `Makefile` and `tasks.sh` exist only at this repository's root, so the
  script lives at `bin/`, not in a template.
- **pymarkdownlnt is pinned.** `.pymarkdown.json` enumerates rules one by one, so a rule a new
  release adds is enabled by default: 0.9.40 added MD049, MD050 and MD051 and turned 9 open
  PRs red (2026-09-18). Bump it deliberately and re-measure the rule set (#383).
- **Validate-meta tests (#407).** The gate blocks merge and had no tests for a missing key, an
  empty value or a dead `scaffold=` path.

### Dependabot (#471, #484)

- Version updates for this repository are monthly, not weekly: the three ecosystems (docs
  venv, `ts-common`'s toolchain, Actions runners) ship no runtime product code, grouping
  already caps noise at one PR per ecosystem per interval, and security updates run
  independently on their own toggle.
- `increase-if-necessary`, not `lockfile-only`: both manifests use caret ranges, so every
  major bump needs a manifest edit, and under `lockfile-only` no major PR would ever open.
- Groups are minor and patch only; a group without `update-types` would bundle majors with
  routine bumps. There is no `labels:` key, because `bin/pr_gate.py` already labels by path
  and Dependabot comments an error on every PR when a declared label does not exist.
- The `eslint`, `@eslint/js` and `typescript` majors are held because their peers
  (typescript-eslint peers on `typescript` below 6.1.0; the react, import and jsx-a11y plugins
  cap `eslint` at 9) exclude them; lift per #720. First match wins, so `@eslint/js` moves in
  lockstep with `eslint`.
- `@types/node` majors are held in both TypeScript tiers (#824, closing #798). The types must
  match the lowest Node a template supports, because newer types let code compile against APIs
  a Node 22 user lacks: the build passes and the program fails at run time. Both tiers pin
  `^22`, the `engines.node` floor line. Lift the `ignore` and raise the pin in the same PR when
  an `engines` floor moves to a newer major.
- Pinning actions by SHA (#369) does not self-update; the Actions ecosystem entry does.
