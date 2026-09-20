# Duskko — execution of the full section-A cut

**Created:** 2026-08-16 · **Base:** `main` @ `198d09d` (PR #177 + #178 merged, no release)
**Origin:** the "Recommendation" from `duskko-blockers_20260816_110000.md`, owner's choice:
**groups 1–5**

This file is the execution record. The triage file remains the source of the *why* behind
each issue being in the queue; this one holds the *state* of each.

⚠️ **Scaffolding is a one-shot copy.** Everything that lands after duskko's `make new` becomes
a manual backfill (#109). That's why these 11 issues come before the scaffold.

---

## PR sequence

Related issues travel on the same branch/PR — splitting by issue would produce 11 PRs
touching the same `templates/python-common/` files.

| PR | Group | Issues | Topic |
|----|-------|--------|------|
| A | 1 | #126, #146, #156, #123 | CI/commit friction that already bit this repo today |
| B | 2 | #141 | documentation-language gate (bilingual project, 2 devs) |
| C | 3 | #128, #120, #150 | ingestion core — duskko's product |
| D | 4 | #119 | `queries/<engine>/` + `load_query` — what duskko replaces with the API |
| E | 5 | #125, #122 | Werner's corporate Windows box |

---

## PR A — CI/commit friction (group 1) — ✅ DELIVERED

Branch `feat/ci-friction-gates-126`. Verified: **5/5 Python tiers** via
`bin/ci/scaffold_lint_test.sh`, unit + integration.

- [x] **#126** — the issue's premise was **stale**; the measured root cause was different
      - [x] measured: in the **template** `codespell` is **no longer** registered on the
            `commit-msg` stage — #158's `default_stages` closed that. `pre-commit run
            codespell --hook-stage commit-msg` responds *"No hook with id `codespell` in stage
            `commit-msg`"*.
      - [x] the real root cause: `default_stages` **was never applied to this repo's config**,
            so the 5 local `always_run` hooks (incl. **two `mkdocs build --strict`**) ran
            twice per commit. Fixed.
      - [x] vocabulary: measured, not guessed. The two `.codespellrc` files diverged in
            **both directions** (30 words missing from the template, 25 from the root) and the
            **stale side was the template** — meaning only generated projects paid for it.
            Union applied.
      - [x] **new gate `bin/ci/check_codespell_sync.sh`** — the word isn't the root cause, the
            divergence is. Negative control proven in both directions.
      - [x] pre-flight: `make check_commit_msg FILE=<p>` / `FILE=<p> ./tasks.sh check_commit_msg`.
            Uses `pre-commit run --hook-stage commit-msg`, i.e. **the project's own hooks** — it
            cannot diverge from what the commit will require.
      - [x] the `*.txt` trap **stopped existing**: using pre-commit instead of calling
            `codespell <file>` by hand, there's no `skip` list in the path.
      - [x] 🔴 **bonus finding along the way:** `tasks.sh` called `print_status` without ever
            sourcing `lib/common.sh`. Measured: `./tasks.sh init` exited **127** in
            `enable_repo_rules` — so `enable_repo_rules` and `enable_security` **never ran on
            any scaffolded project**. Invisible to anyone using `make`, and `tasks.sh` is
            exactly the interface for the **no-make** box (Werner's Windows). Fixed + tested.
- [x] **#146** — pre-push guard: a non-empty index means the commit is rejected
      - [x] `bin/check_clean_index.sh` + a `local` hook on the `pre-push` stage
      - [x] `--hook-type pre-push` was already installed by `bin/precommit.sh` — confirmed
      - [x] should-fail + **mutation proof**: disabling the guard, exactly the negative-control
            test fails; restored, it passes
      - [x] guards the **index**, not the dirty tree (an unstaged edit at push time is routine)
- [x] **#156** — `actionlint` gate (`yamllint` doesn't validate a workflow)
      - [x] premise **verified in the same file**: `yamllint` exit **0**, `actionlint` exit
            **1** on `pull_request_review_thread`
      - [x] `bin/lint_actions.sh` (resolves, doesn't install) + hook + CI + `Makefile`/`tasks.sh`
      - [x] fails when discovery matches **zero** files — proven
      - [x] `find` grouped — proven with a **directory** named `decoy.yaml`
      - [x] CI installs a pinned version **with SHA-256 verified**; `LINT_ACTIONS_REQUIRED=1`
            turns the graceful skip into a failure (a skip in CI is a placebo)
      - [x] `SHELLCHECK_OPTS` at house severity
      - [x] **sibling gate at the root** `bin/ci/check_actions.sh`, which lints the repo's own
            workflows **and the ones inside `templates/`** — it's what would have caught the
            defects below
      - [x] 🔴 **8 real defects found on the first run**, all in workflows that already ship:
            `actions/cache@v3` (a version GitHub **no longer runs**) in 3 tiers,
            `softprops/action-gh-release@v1`, `SC2046` in 2 release workflows, and a
            `workflow_call` output whose expression could only resolve to an empty string (zero
            consumers → removed). 7 fixed; the 8th is a location false-positive.
- [x] **#123** — the work-ledger gate permanently blocks every bot PR
      - [x] exemption by the `[bot]` suffix, at the **I/O boundary** (`pr_author_login`), pure
            rule kept separate (`is_bot_author`)
      - [x] reads `pull_request.user.login` from `GITHUB_EVENT_PATH`, **never**
            `GITHUB_ACTOR`
      - [x] falls back to actor only when there's no PR payload; an unreadable payload →
            **closes**
      - [x] 9 tests, both directions named, incl. the human-as-actor case

**Extra, outside the 4 issues, but needed so they aren't decorative:**
`bin/ci/scaffold_lint_test.sh` only ran `make lint` + `make unit_tests` — never the
**integration** tests, which are the only place a `bin/*.sh` is actually **executed**. Each
tier's 30 integration tests traveled without ever running. Now they run.

**Second extra — `bin/ci/check_test_copy_lists.py`.** The test copy-list is hand-maintained in
each of the 5 scaffolds, and a test forgotten there gets written, committed, and **never runs
in any project**. 🔴 Before the gate, the only available signal was the test **count** — and
nobody compares it against expectations: a run that sums 18 tests and keeps showing 234 stays
just as green as one showing 252. But the count is weak even when read, because an identical
total hides one test that vanished and another that appeared. So the gate doesn't count: it
compares **sets** — the set of shared tests reachable by each scaffold against the set that
exists in `templates/python-common/tests/unit/`, naming every one missing. On the first run
the gate found `test_startup_fragility_order.py` — the guard for #160's own fix — missing from
the 5 tiers. It also documents an honest gap: `lib-minimal` vendors the utils under
`_internal/` and therefore **does not receive their tests** (it would need the same
`rewrite_internal_imports` applied to the tests too).

### CodeRabbit review fixes on PR #180

- [x] **`persist-credentials: false`** on `actions/checkout` — flagged on **1** job; applied
      to all **12** in the file, all read-only. Fixing only the flagged one would leave exactly
      the *precedent* #141 exists to fight.
- [x] **`check_codespell_sync.sh` compared lowercased** — a real bug, mine. codespell splits
      the ignore-list into two (`process_ignore_words`): an already-lowercase entry filters the
      dictionary; a capitalized entry goes into a different set and only matches that exact
      capitalization. So `classe` and `Classe` are **not** interchangeable, and lowercasing
      before comparing would declare "in sync" two configs that behave differently — the gate
      blind to the exact drift it exists to catch. Now compares verbatim **and** rejects an
      entry carrying a capital.
- [x] **`pr_author_login` failed open** when `GITHUB_EVENT_PATH` was set but the file was
      missing: it fell back to `GITHUB_ACTOR`. Inside a workflow the payload is the only
      authority; any failure to use it now returns `""`. Named test added.
- [x] **MD018** in the ledger — a line starting with `#117`. Rewritten as a list, which
      resolves it structurally instead of depending on where the line wraps; a sweep confirmed
      0 across all of `docs/backlog/`.

## PR B — language (group 2) — ✅ DELIVERED

Branch `feat/docs-language-gate-141`, stacked on PR A. Verified across **5 tiers**.

- [x] **#141** — `bin/check_comment_language.py` **ported** from `recon_al_cvm` (494 lines,
      already field-calibrated) instead of rewritten. The ladder: reuse what exists and works.
      - [x] the calibration came along and was **proven by mutation**: removing the acronym
            wording, the punctuated-token one, the length preservation, or the per-line escape
            scope makes **exactly 1** test fail. None of the 4 rules is decorative.
      - [x] 18 tests named by false-positive class in
            `tests/unit/test_comment_language_gate.py`
      - [x] positive + negative control: catches real Portuguese (2 findings, right line) and
            passes the 6 measured false positives (accented labels, Microsoft's `COM`,
            `emails.yaml`, `bradesco.com.br`, a URL with `/para/que/nao`, a quote spanning 2
            lines)
      - [x] **the templates already pass**: 129 files swept across the 6 folders, 0 findings —
            the gate enters green, not with debt to pay down
      - [x] two improvements over the original, both lessons from this session: **fails when
            discovery matches zero files** (otherwise it passes vacuously forever) and **prints
            the count on success** (a silent gate is indistinguishable from an absent gate —
            measured: 118 files in mvc, 142 in ddd-native, 78 in lib-minimal)
      - [x] wired into the 4 surfaces: hook, `make lint`, `tasks.sh lint`, CI step
      - [x] added to the 5 copy-lists — and PR A's `check_test_copy_lists.py` gate **proved**
            it (26 → 27 shared tests, all reachable)

Per-tier count after B: mvc-native **256**, mvc-orm **256**, ddd-native **251**, ddd-orm
**251**, lib-minimal **89** — all +18, and 30 integration each.

## PR C — ingestion core (group 3) — ✅ DELIVERED

**PR #186 merged** (`b130c6e`). The detailed record lives in
`ingestion-core-seams_20260817_083243.md`; only the state is kept here.

- [x] **#128** — ingestion contract discipline (8 lessons) + name-collision and `__all__`
      population gates
- [x] **#120** — `raw_workspace` seam (bronze artifact retention)
- [x] **#150** — cache the daily-stable vendor download inside the seam

## PR D — queries / SQLite (group 4) — ✅ DELIVERED

**PR #191 merged** (`fa5ea9f`), issue #119 closed, released as `v0.15.5`. Branch
`feat/queries-engine-layout-119`, cut from `main` @ `fdba82a`.

- [x] **#119** — `queries/<engine>/` layout + `load_query` resolver + runtime guard for
      git-ignored config (`src/config/queries/` existed and was **empty** in both native tiers)
      - [x] **derive, don't check**: `config/queries/<engine>/<table>__<purpose>.sql`. The engine
            is a **directory**, never a filename prefix — a prefix declares the engine a second
            time and can then disagree with the first. No code path hands T-SQL to a SQLite
            connection, so nothing has to notice.
      - [x] pure `load_query(str_filename, str_backend, path_queries_root)` in
            `templates/python-common/src/utils/queries.py` — the rule separated from the I/O
            boundary (same shape as `is_bot_author` / `pr_author_login` from #123). The thin
            per-tier caller (`src/config/query_loader.py`) injects the engine and the root.
      - [x] **`active_backend()` is the single reader of `DB_BACKEND`** — mvc-native in
            `config/connection_db.py`, ddd-native in
            `chassis/db_schema/application/database_factory.py`.
      - [x] the loader **refuses** a name carrying a directory component: spelling the engine
            there would route around the very check it exists to make
      - [x] the error **distinguishes** a wrong backend from a wrong name — it lists the engines
            whose directory *does* carry the file (`EXISTS for: mssql, oracle`), or says
            `exists for no engine` plus the directories present. Without that, a typo and a
            misconfiguration read identically.
      - [x] **8 tests** in `tests/unit/test_queries.py`, named per failure class, with a
            **mutation proof**: swapping `/ str_backend` for a glob fails exactly the routing
            test; restored, it passes.
      - [x] an example `.sql` per engine carrying the `database / table(s) / purpose` header, the
            two **deliberately different** (`TOP (n)` vs `LIMIT n`) so the routing is observable
            rather than decorative, and capped identically so one filename stays one contract
      - [x] 🟢 **measured bonus from the lesson:** sqlfluff resolves config **per directory**, so
            each `queries/<engine>/.sqlfluff` declares its dialect and **one pass** covers both.
            Deleted the (rejected) "run one pass per `--dialect`" advice from `.sqlfluff`,
            `.sqlfluffignore` and `bin/lint_sql.sh`. Negative control proven: removing
            `mssql/.sqlfluff` makes the T-SQL `Found unparsable section` under `dialect=sqlite` —
            the production failure reproduced inside the linter; restored, exit 0.
      - [x] `.env.example` **sectioned by scope** in the 4 tiers reading `DB_BACKEND` (not only
            the native ones): the flat list is the union of six backends, so five sixths of it is
            inert while reading as live configuration. Each block now names the `DB_BACKEND`
            values that actually read it.
      - [x] the `tasks.sh init` AC was **already satisfied** — `bin/ensure_env.sh` never
            overwrites an existing `.env`. That is correct (it must not clobber credentials) and
            is exactly what makes drift permanent, so the runtime guard is the backstop.
            Documented with a ⚠️ in `src/config/CLAUDE.md` rather than left as tacit knowledge.
      - [x] docs: a "derive, don't check" section plus the guard-routing table in
            `templates/python-common/src/config/CLAUDE.md`, both `docs/py-*-service-native-db.md`
            pages, and the "Adding a new DB backend" entry in both tier CLAUDE.md files (the old
            instruction pointed at a dict that no longer exists)

**Verification:** 8 root gates green (copy lists: **32** shared tests reachable from all 5 tiers,
spell, shell, actionlint, meta, version sync, codespell sync, docs build) plus all 5 tiers via
`bin/ci/scaffold_lint_test.sh`.

### 🔴 Found along the way: mypy's `exclude` does not cover an imported module (#190)

Adding `config/query_loader.py` turned **ddd-native red with 20 mypy errors** in
`chassis/db_schema/infrastructure/*_handler.py` — files this work never touched.

`mypy.ini` carries `exclude = ^chassis/`, but **`exclude` filters file DISCOVERY only, not a
module reached through an `import`**. That exclude held only while nothing outside `chassis/`
imported it — a property of the application's wiring, not of the config. `query_loader` imports
`database_factory` (to read the active backend), which imports all six handlers: **31 → 33 files
checked**, and 20 long-standing errors surfaced for the first time.

Fix: `[mypy-chassis.*] ignore_errors = True` — `ignore_errors` is the setting that follows the
module, making true the intent the `exclude` comment already stated. After it:
`Success: no issues found in 33 source files` (the 2 extra files are still checked; only the
chassis errors are silenced). The real debt is tracked in **#190**.

⚠️ **Two wrong hypotheses before the right measurement** — recorded because the cost was real:

1. *"It is `mypy = ">=1.8.0"` with no ceiling letting the 2.x major in."* Plausible and false. A
   `<3.0` cap **excludes nothing** (2.3.1 satisfies it); a `<2.0` cap resolved **1.20.2** and
   failed identically, with the same 20 errors plus one. The version was never the variable. Both
   caps were reverted.
2. *"It is pre-existing, not my change."* Also false. The control that should have run **first** —
   the same tier on a clean `origin/main` — passes: `Success: no issues found in 31 source files`,
   on the **same mypy 2.3.1** that had been accused.

Procedural lesson: **"none of my files appear in the error list" is not evidence that my change
did not cause the errors.** An import edge changes *what the checker looks at*, so a file nobody
edited starts failing because of an edit somewhere else. Run the clean-tree control before
theorising about the dependency.

### CodeRabbit review on PR #191 — 6 accepted, 1 refused

🔴 **The serious finding was mine and was exploitable.** `load_query` validated the *filename* as
a single segment and accepted **anything** as the *backend*. That yields **two** distinct
mechanisms, worth separating because a guard catching only one leaves the other standing:

1. **Parent traversal** — `DB_BACKEND=..` resolves `<root>/../<file>`, walking one level out of
   the queries tree. Reproduced before fixing: without the guard it returned `'ESCAPED-SECRET'`
   from a file seeded outside the root.
2. **Root discard via an absolute path** — `DB_BACKEND=/somewhere-absolute` traverses nothing:
   `pathlib`'s `/` **discards the left operand** when the right is absolute, so the queries root
   simply stops participating in the path. No `..` involved.

Validating one operand and not the other was the defect. Both now share one rule (which rejects
both cases above, plus `.`, empty, and separators of either flavour), and `active_backend()`
validates against `SET_BACKENDS` in both native tiers. This undid the asymmetry the PR had called
deliberate: the DDD builders now take the backend as an argument, so the map lives at module
level and the engine names have **one** source. The old justification was true of the code as
written — but the code did not need to be written that way.

Other accepted findings: `DB_PORT` now ships **commented out** in all 4 tiers (the per-backend
default already existed in `_compose_dsn`; the seed was defeating it for five of the six
engines); `LIMIT 1000` added to the sqlite variant to match the mssql `TOP (1000)` (one filename
is one contract — the result set must not depend on the backend); the `.sql` header corrected
(measured: SQLite **accepts** bracket quoting and rejects `TOP`, the opposite of what I had
written in the file that teaches the convention); the `.env` visibility claim narrowed in all 4
places the sentence had been copied to; `DB_ODBC_DRIVER` quoted; the stale Poetry comment in
`lint_sql.sh` refreshed (staleness introduced by my own edit).

**Refused:** alphabetical `.env.example` ordering. dotenv-linter's `UnorderedKey` interleaves the
scope blocks that #119 exists to create, and dotenv-linter is not a gate in this repo. Argued on
the merits in the thread, with the door open if it ever becomes a real gate.

⚠️ **Three rounds lost in series** on the same file (`S108` → `ERA001` → `ruff format`), all
invisible outside the harness. The generated project's `make lint` **short-circuits**, so each
round reveals only the first error — declaring "the threads are handled" before running the gate
cost roughly 12 minutes of serial discovery.

### 🔴 Recurring CI hang (#192)

The `Scaffold + lint + test` job hung on the `Install scaffold tooling (envsubst)` step **twice in
two days** (#188: 6h0m15s until GitHub's limit; #191: cancelled by hand). It is **not** a missing
`-y` (checked — the flag is already there): it is `apt-get update` against a network that never
answers, with nothing bounding it. Two defects: the step installs a package the runner **already
has** (its own comment says so — the install exists only for `act`), and `grep -c timeout-minutes`
returns **0** across 13 jobs, so GitHub's 6-hour default applies. Widened by the wrap-up audit:
**9 of 9 template workflows** also carry zero `timeout-minutes`, so every scaffolded project
inherits the same shape. Filed as **#192**, outside this PR.

## PR E — Werner's Windows box (group 5) — ✅ DELIVERED

Branch `fix/windows-box-handoffs-125-122`, cut from `main` @ `3530771`. Verified on **all 5
tiers** via `bin/ci/scaffold_lint_test.sh` (unit + integration) and `make lint` at the root.

- [x] **#125** — the issue asked to pin the plugin "in the bootstrap installer"; the premise had
      **moved since it was written**, and checking that first changed the deliverable
      - [x] 🔴 measured: **no template recipe called `poetry export`**. The target (`export_deps`)
            was removed in `14cd52f`, and the root `CLAUDE.md` still advertised
            `make export_deps` — documentation for a command that did not exist
      - [x] the `poetry-plugin-export` dev-dep in all 5 tiers was **dead code**: a plugin
            installed into `.venv`, where no Poetry lives to load it. Removed — the honest fix
            is one source, not two
      - [x] plugin pinned in `requirements.txt` (what `ensure_poetry` installs from). A dev-dep
            reaches the project venv and nothing else, so the recipe would work from an
            activated shell and fail from cron, from CI, and from the offline host it exists to
            serve
      - [x] ⚠️ **the owner's call corrected my direction**: calling `poetry export` directly was
            wrong — `bin/poetry_exec.sh` / `ensure_poetry` exists precisely for limited-access
            boxes. `bin/export_deps.sh` **reuses** that machinery instead of re-deriving the
            resolution, and the house rule (never a bare `poetry`) falls out for free
      - [x] the lesson's **diagnostic half** implemented: the export output is **captured and
            re-printed** on failure, and the remedy names `${POETRY_CMD[*]}` — the binary that
            actually failed — never a bare `poetry`. Never `>/dev/null 2>&1` a command whose
            failure you then explain: the explanation becomes a guess about text you refused to
            read
      - [x] gate on all **4 surfaces**: `bin/export_deps.sh`, `Makefile`, `tasks.sh`, docs
            (`python-common/CLAUDE.md` + `bin/CLAUDE.md` + the root `CLAUDE.md`)
- [x] **#122** — `to_absolute` made public, called at both Outlook COM hand-offs
      - [x] `_to_absolute` → `to_absolute`; it was private, so nothing could reuse it — which is
            exactly why the lesson is flagged **RECURRED**
      - [x] the two real hand-offs: `Attachments.Add` (send) and `SaveAsFile` (download). The
            `subprocess` sweep across the DB handlers was a **false alarm** — `mysqldump` writes
            to *our* file handle (`stdout=handle`), so the path never leaves the process
      - [x] both mechanisms documented in the docstring, because only the first is obvious:
            CWD-relative re-anchors in *their* directory; and on Windows a POSIX-shaped value is
            **drive-relative** (rooted but driveless → `is_absolute()` is `False`), so it lands
            on whichever drive the reader sits on. Both invisible to an `exists()` guard, which
            runs in **our** process
      - [x] the Windows mechanism is **pinned on POSIX CI** with `PureWindowsPath`, otherwise it
            is unobservable off a Windows box
- [x] **negative control on both**, proved by mutation in a real scaffold:
      - reverting only the send hand-off → fails **exactly**
        `test_send_email_hands_com_an_absolute_attachment_path` (1 failed, 315 passed)
      - swapping the capture for `2>/dev/null` → fails **exactly**
        `test_export_deps_reprints_what_poetry_said_on_failure` (1 failed, 31 passed)
      - ⚠️ the first two mutation attempts were **invalid**: lint short-circuited ahead of them
        (`F841` orphan variable, then `F401` orphan import) and the test never rendered a
        verdict. A mutation must produce the genuine *pre-fix* code, not code broken in a way
        some other gate catches first

### CodeRabbit review on PR #198

- [x] **the Windows test asserted the stdlib, not our code.** It pinned
      `PureWindowsPath(...).is_absolute()` and never called `to_absolute`, so a regression
      handing the driveless input straight back would still have passed. It now simulates the
      platform verdict and calls the real function. ⚠️ The neighbouring relative-path test did
      already catch that regression — but a test whose only assertions are about the standard
      library is defending nothing of ours.
- [x] **ledger prose switched to en-US.** The convention had already turned over in the PR D
      section; my PR C and PR E entries were the ones out of step.

## Verification (every PR)

- `bash bin/ci/scaffold_lint_test.sh <tier>` on **each affected tier** — not only at the root.
  Verify against the version the **generated project** pins, never against the template root
  (lesson `verify-with-the-version-the-project-pins`).
- Every new gate needs a **negative control** (proving it can fail), and an entry in the
  scaffold's **hand-maintained copy-list** — the tell is the test **COUNT**, never the color
  (lesson `a-new-test-must-be-added-to-the-hand-maintained-copy-list`).
- A gate lives on **4 surfaces**: pre-commit hook, CI step, `Makefile`, `tasks.sh`
  (lesson `wire-a-gate-into-the-recipe-developers-actually-run`).
- Kanban cards: the hook only moves the card of the issue that started the branch. Bundling N
  issues leaves N-1 cards stuck — **move them by hand**.

## State (end of the 2026-08-16 session)

- **PR #180 merged** (`3a6a7f9`) — group 1. **PR #182 merged** (`b039a42`) — group 2.
- Issues closed: **#126, #146, #156, #123, #141, #174**; cards in Done.
- **#173** commented on: hole 1 of 3 closed (`required_conversation_resolution: true`).
- ⚠️ **Release pending: v0.15.4.** Nothing has been cut since v0.15.3.
- **Groups 1–5 delivered.** Remaining: the release and the duskko `make new`; #192 (the CI
  hang) stays open, outside this cut.

### What the session found beyond the scope

The review-threads gate had **passed vacuously from the very start** — it compared the
roster's REST spelling (`coderabbitai[bot]`) against what GraphQL returns (`coderabbitai`).
That is how #180 merged with 2 open threads. Replaced by four layers, the decisive one being a
**`Stop` hook** that refuses to end the turn with a pending thread (dotfiles-dev PR #127) —
because blocking the merge prevents a bad outcome, but it **doesn't drive the work**.

---

## Outside this cut

Triage sections B and C, plus the section-A items left out of groups 1–5:

- ingestion and data: `#116`, `#144`, `#148`, `#117`, `#127`
- generated-project CI and docs: `#111`, `#145`, `#130`, `#113`, `#110`, `#124`, `#152`
- deliverable and email: `#118`, `#121`, `#151`, `#161`, `#162`

Backfill is cheap while duskko doesn't exist yet; after it, it becomes `#109`.

## Next

`make new` → python → `mvc-service-native-db` → name `duskko`.
