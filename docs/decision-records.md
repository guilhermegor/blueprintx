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

## Generated-project test suite (`templates/python-common/tests`)

The tests every Python scaffold ships carry no comments. The shapes below recur across the
suite; each exists because a simpler form was measured to be wrong or to hide a failure. The
module layout the old banners spelled out is plain order now: helpers, fixtures, then tests.

### Shapes forced by the complexity ceiling

`tests/` is held to cyclomatic complexity 1 by `bin/check_complexity.sh`, so a test body has no
branch. That is the mechanical form of "a test exercises one path"; a branch in a test means the
green never says which side ran.

- **Comprehensions, generators and `contextlib.suppress`** replace loops with skip guards,
  `try` handlers and flag variables: mccabe charges a comprehension nothing and charges every
  loop, guard and handler a point (`test_startup_fragility_order`, `test_contract_family_conventions`,
  `test_integration/test_bin_scripts`, `test_wheelhouse_select`). A short run of three calls or
  entries is written out rather than looped for the same reason.
- **`skipif` decorators over a body guard.** An environment probe is resolved once at import time
  and feeds a `skipif`, because `if ...: pytest.skip(...)` in the body reads as a path through
  the test to a reader and to mccabe alike. The same applies to "does this tier ship the package
  or driver" (`test_all_exports_gate`, `test_daily_cache`, `test_ruff_ret_rule`, `lint_deps`).
- **Module-level helpers and stubs, never nested `def`s.** A nested function costs the enclosing
  test one point, so a branch-free stub would spend the budget reserved for branching
  (`test_pr_gate`, `test_sidecar_metadata`, `test_retry`).
- **`Mock(side_effect=[...])` for a flaky callable** (`test_retry`, `test_review_retry`): the call
  sequence "raise, raise, return" is data where a reader looks for it, not an `if` on a counter,
  and `functools.wraps` tolerates a Mock. A conditional expression keeps the opt-out fixture in
  `conftest.py` at complexity 1: a test that opted out is patched back to the real primitives,
  a no-op that monkeypatch undoes at teardown anyway.
- **`parametrize`, not a `for` in the body.** A loop asserts N cases behind one green: the report
  cannot say which case ran and the first failure hides the rest. A reference date, one token
  map and three documented tokens is one assertion over different keys (`test_paths`).
  Where a case list must be flattened, flatten first and assert once on the collected names so
  every offender is reported (`test_startup_fragility_order`).
- **An immutable default for env-override parameters.** A mutable `{}` default is a bugbear B006
  finding and a `dict_extra or {}` guard costs a decision point; short-circuit evaluation makes
  a helper an expression instead of a branch (`test_bin_scripts`).
- **One build, several facets.** The "expensive shared setup" pattern in `tests/CLAUDE.md`,
  module-scoped, stops the one-assert rule from turning three claims about one read-only frame
  into three rebuilds of it (`test_frames`, #544). `pytest.raises` plus its `match=` is one
  assertion site with one failure mode, not two (`test_pip_requirements`).
- **Split rather than combine.** A conjunction in one assertion reports only that the whole was
  false: an absent loader and an absent spec are different faults (`test_all_exports_gate`,
  `test_layer_imports_gate`, `test_review_retry`). An introspective test over `__all__` beats
  five hand-listed imports, so a name added to a package without being exported is what fails
  (`test_retry`, the surface added in #116).

### Witnesses and negative controls

- **Every gate needs a test that has seen it fail** (#111). A gate with no should-fail witness
  is indistinguishable from one that is not wired up, since both print green. Writing the first
  eight found three live defects: `check_provenance.py` and `check_docstrings.py` both exited 0
  printing nothing when their cwd-relative globs matched nothing, and `lint_actions.sh` accepted
  any file named `actionlint` on `PATH` as a working one. The `lint_*.sh` wrappers need a
  witness for both the missing-tool branch and the zero-discovery branch, since "tool not found"
  and "tool ran and passed" look identical from outside.
- **A healthy tool is required for the zero-discovery witness.** With actionlint absent the run
  stops in the required-tool branch and never reaches discovery, so an assertion that also
  accepts "required" stays green with the guard deleted. Poetry is shadowed there so resolution
  cannot take the vendored path.
- **A fixture must reach the boundary it claims to test.** A 100-digit input sat under Python's
  4300-digit conversion limit, exercised only the `OverflowError` path and passed while the
  `ValueError` path was open; it is 5000 digits (`test_review_retry`). A multi-line docstring
  that closes on a line starting with text is required for #206's third shape: a one-line
  docstring matched the old start-anchored guard and proved nothing. Fixture halves that a gate
  keys on disagreement over must genuinely differ (annotated `-> int`, documented as `str`).
- **A scanned-nothing control keeps a gate from becoming decorative.** A gate that scanned
  nothing also found nothing wrong and would report OK forever after a rename; the zero-discovery
  and could-not-parse cases pin that for each gate (`test_all_exports_gate` and siblings).
- **Real wording, verbatim.** The reviewer's refusal text and declared wait come from the live
  message (#275, 2026-08-26): the phrase is the interface, and a paraphrase would test our idea
  of the message while the parser only ever meets the real one (`test_review_retry`).
- **Relative paths where the gate takes relative paths.** `swallowed_by_omit` is called with a
  relative `path_module` after a `chdir` to the project root. Passing an absolute path makes each
  test vacuous: it matches the absolute branch and the relative pattern is compared with a path
  that can never match. With the absolute branch reverted out of the gate, the earlier versions
  still reported `2 passed` (`test_coverage_floor_gate`). Gates that derive `PATH_ROOT` from
  `__file__` (`check_docs_code_refs.py`, `check_function_length.py`) are pointed at a throwaway
  tree with `--root`, because `cwd=` alone would scan the real repo.

### The dual import root

`pytest.ini` puts both `.` and `src` on the path, so one file is importable as `utils.x` and as
`src.utils.x`, and Python loads it twice with distinct class objects. A module that annotates a
parameter with a class it imports bare (`ProblemReport`, `FileContract`, `RegimeWindow`,
`LogEmitter`) is guarded by beartype or the runtime TypeChecker, whose nominal check rejects an
instance built from the other copy. So these tests import bare (`utils.`, `config.`), never
`src.utils.`; `tests/CLAUDE.md` ("The dual-import-root trap") has the rule. The names are
interchangeable until a class crosses between them. Affected modules: `test_daily_cache`,
`test_provenance`, `test_regime_adapters`, `test_ms_office_excel_sheet_names`, `test_xml_reader`,
`test_sidecar_metadata`, `test_config_schemas_example`, `test_contract_oracle_example`.

### Per-suite notes

- **`test_bin_scripts` (integration).**
    - Subprocess argv is a constant, trusted list built from repo-internal paths with no shell,
      so bandit's subprocess warning is a false positive; each call carries its own `noqa`.
    - The environment is inherited, not scrubbed: an emptied `PATH` takes `dirname` with it, so
      `SCRIPT_DIR` never resolves and the run fails for a reason unrelated to the claim
      (measured). `poe_exec.sh` is run under either branch of the resolver, since a resolved Poe
      and the "none found" diagnostic are both built from `print_status`, so either proves the
      lib is reachable.
    - `poetry_exec.sh`: stdout is exactly the project version, and the resolution status lands
      on stderr. `precommit.sh`: the skip-gracefully default exits 0 and announces the skip
      without fabricating a repository or running `git init`; with a real work tree a throwaway
      `HOME` isolates the global `safe.directory` write, and the self-heal never emits the
      "no git repo" skip.
    - `pip_fallback.sh` driver pruning: `config/connection_db.py` lowercases `DB_BACKEND` before
      dispatching, so those spellings are valid configuration and the pruner must agree, or it
      drops the one driver the project uses.
    - `bin/check_*.py` on Windows: cp1252 stdout must not crash the glyph that `check_dtypes`
      prints for a banned binary float dtype.
    - `bootstrap.sh`: a corporate CA must be unioned with the existing roots, never replace them.
      A replacement writes exactly one block, while only a union carries the roots too. certifi's
      absence is simulated by hiding it from the child with a finder written against the modern
      protocol: the older two-method form was dropped in Python 3.12 and a finder shaped that
      way is skipped without a warning. The supported path reads the store the browser trusts.
    - `get_corporate_ca.sh`: the refusal carries the remedy, not only the verdict, and nothing is
      written on the refusal path. `check-clean-index`: editing a tracked file without staging it
      leaves the tree dirty and the index empty, the routine state the guard must never block;
      `git add` with no commit consuming it is the fingerprint of a rejected commit, and the
      verdict names the likely cause, the file and the remedy including the escape hatch.
    - `export_deps.sh`: Poetry's own words survive to the operator, and the remedy names the
      resolved binary, not a bare `poetry`. `print_status`: an unknown status must not look like
      ordinary output.
    - `check-urls` (#206, #224): every docstring shape must actually be scanned. The three shapes
      each hold the same unreachable URL, so a shape that reports clean is a check nobody ran.
      The third (a closing delimiter sharing a line with text) was never blind, since the URL was
      scanned as body text, but the state never flipped back, so every later line was read as
      still in the docstring. The cache key mirrors the hook's own `md5sum`, not a security use.
    - `check_complexity.sh` (#167, #254): a function with complexity 3 (two `if`s plus the
      implicit path) is over `src/`'s ceiling of 2 and under `bin/`'s 8. The colour-control
      variables are stripped from every run so a developer's shell cannot decide what the suite
      measures; the ANSI CSI pattern is matched so escapes never reach the gate's parsing;
      the reported finding is a regex over the whole line, and `print_status` adds colour, so
      only the ruff-derived remainder after `C901` is asserted clean.
    - `rerun_stale_gate_runs.sh`: a scriptable `gh` shadows the real one and records every call.
      Shadowing, not mocking, because it is deterministic on any machine including CI, where
      the real `gh` is installed and a `skipif` would drop the coverage where it matters. It
      does not evaluate `--jq`: filtering is GitHub's job, so the tests assert on the query sent.
    - `lint_deps.sh` (#238): the manifest declares nothing, so any third-party import under
      `src/` is undeclared by construction. PEP 621 is used rather than `[tool.poetry]`, which
      does not drift when the tier's Poetry moves. The test imports a package every tier
      declares, installed in the venv yet absent from the throwaway manifest: present at run
      time today and gone the day whatever pulled it in stops doing so. The wrapper's `shift 2`
      drops `run` and `deptry`, leaving its own arguments.
    - `run.sh` (#252): an argument passed to `poe run <x>` must reach the entrypoint; the test
      file is made newer than `pyproject.toml` with a margin so the `-nt` check in
      `runtime_env_needs_bootstrap` is unambiguous at any filesystem mtime resolution.
    - `test_resourcewarning_unraisable_gate`: constant trusted argv from `sys.executable` and
      repo-internal paths, so the bandit warning is a false positive.
- **`test_backlog_ledger` and the integrity gates.** `classify_risk` returns the single most
  dangerous class and ranks `tests` above `ci`, so a branch touching `bin/` and `tests/`
  collapses to `tests`, not a ledger class. One test pins that collapse, the other that asking
  per path still catches it; they are two tests because they assert different functions. The bot
  exemption (#123) is tested in both directions by name, because an exemption is one
  `return 0` from disabling the gate for everyone with the suite green. `robotics-team` and
  `dependabot` are the load-bearing cases: "bot" inside a name is not the suffix, and only
  GitHub's own marker counts. A gate demanding a human-authored artifact otherwise blocks every
  bot PR. Gate integrity (#309) is pure logic, offline; assertion integrity (#324) covers a
  test's expected value edited to match a bug, with the line number as a case, since a finding
  that cannot point at its assertion sends the author hunting. A renamed test file is read at
  its source path (#590), with padding to keep git's rename similarity above 50% after the
  one-line weakening; an expected-value change counts only when production code also changed
  (#289 is the live example). The `#334` review added three ways the guard could be defeated or
  misfire.
- **`test_pr_gate`.** Terminality differs from display state: `{"a": "failure", "b": "pending"}`
  displays as failure while not terminal, and breaking the poll loop on `gate_state() !=
  "pending"` would stop on the first transient red while other checks run, with nothing
  re-rendering the comment afterwards.
- **`test_regime_adapters`.** `resolve` returns the first covering window while the registry
  promises windows may arrive in any order, so two overlapping windows bind a period to whichever
  was listed first, a reader parsing a real file against the wrong published header with nothing
  reporting it (#344 review). Validation the caller can undo is not validation, hence the
  regression for it.
- **`test_paths`.** The premise (`PureWindowsPath("/home/x/out")` is rooted but driveless, so
  `is_absolute()` is False) and the behaviour (the function routes through `resolve()`) are
  separate claims and must not collapse (#544): asserting only the premise pins the platform and
  leaves our function untested, since a regression handing the driveless input back would pass.
  On POSIX CI the verdict is simulated and the real function is then called under it.
- **`test_daily_cache`.** `write_bytes` is not atomic, so an interrupted run can leave an empty
  file; serving it hands the caller a valid-looking path to nothing that fails later and far
  away. The miss, the hit on the same reference day, and the half-written file each get a case.
- **`test_frames`.** An empty frame with no columns makes the shape data-dependent: a caller that
  concatenates or renders it behaves differently depending on whether rows existed. Returning the
  declared columns keeps it constant; both seams owe the property, empty and still shaped.
  `apply_dtypes` needs disjoint column sets, so a date column is declared by `list_date_cols`
  alone, never also in `dict_dtypes`.
- **`test_startup_fragility_order`.** The reference block is an optional override and must never
  force a project to declare a source's `{dir, pattern}` twice; the tests pin the fallback chain
  (override wins, the real input's own spec otherwise, `None` only when neither exists), with the
  absent-override path asserted explicitly since every existing project has no `reference_files`
  and that path is where a regression lands first. The try-block check is scoped to the one that
  wraps the config read, since the module has a legitimate `except ModuleNotFoundError` for the
  typing shim. These tests live in this module because a new `tests/unit/*.py` needs its own
  scaffold copy-list wiring (`bin/ci/check_test_copy_lists.py`).
- **`test_contract_family_conventions`.** The list of column names two contracts legitimately
  share stays empty by default and a conscious list: two sources requiring `cnpj` is ordinary, so
  the check's value is that sharing is declared, not forbidden.
- **`test_comment_language_gate`.** Two consecutive comment lines form a quotation that opens on
  the first and closes on the second; read line by line, the opening quote never meets its
  closing one, the quoted span survives redaction and its language is charged to the English
  comment. Each false positive was measured and is pinned by name, accented capitals included
  (`NÃO`). The environment is inherited because a bare dict drops `PATH`; discovery reads
  `git ls-files` (#331), so an untracked fixture tree is invisible and the fixture must be a
  committed repo, with an orphan worktree stand-in present on disk but never staged. One
  representative long-lived file per location the allow-list once missed is checked.
  Registering the module root makes teardown undo the rebind the gate performs.
- **`test_comment_budget_gate`.** The ratchet ceiling, the escape hatch, pragma lines breaking
  a run, the decorative banner (regex-decidable, no ratchet), positional exemptions, the
  extensionless `Makefile` as the issue's own worked example, and that Python files are checked
  (#466).
- **`test_logs`.** A `StreamHandler` flushes on every record, so the old flush loop was dead
  code; the caller prefix is rebuilt by walking the stack, so the pattern asserts the shape and
  ends at the message, which also proves it was written; closing a `FileHandler` sets its stream
  to `None`, a deterministic signal independent of garbage collection.
- **`test_raw_workspace`.** The criterion is what is not on disk afterwards, so the assertion
  runs outside the block. A caller naming a leaf inside an unbuilt tree must not assume the
  parent exists, or a bronze write dies on the first run of a new dated folder. The runtime
  checker guards against the string form, which would otherwise fail at `str.mkdir` later.
- **`test_tabular_reader`.** A stray quote opens a free-text middle column; under default quoting
  the open quote swallows the separator and the trailing rows, while `QUOTE_NONE` keeps the three
  real fields.
- **`test_typing`.** Under the default policy a bool is rejected where an int is annotated;
  flipping the strict-bool knob off on the seam and rebuilding the config makes the bool satisfy
  it, proving the knob and not the adapter drove the change.
- **Smaller notes.** `test_decimals`: equality alone proves finiteness since NaN never compares
  equal, and a plain float-repr cell keeps its value and is not inflated tenfold.
  `test_docs_code_refs_gate` and `test_verify_venv_imports`: `in None` raises, so a missing
  finding fails there too. `test_dead_code_gate`: the duck-typed stand-ins for vulture's `Item`
  are a flat literal down to the one field read, not a comprehension.
  `test_family_convention_example`: the illustrative family stands in for `import myproj.section
  as family`; in a real project it is `family.__all__`, the declared public surface, and the
  members are discovered from it, never hand-listed. `test_env_config`: only `_dev` exists.
  `test_ruff_ret_rule`: the shipped config the test is the witness for is found by walking
  `tests/unit/ -> tests/ -> python-common/`. `test_wheelhouse_select`: built through `map`.

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

## Generated-project workflows (`templates/python-common/.github`)

The workflows and `dependabot.yml` a Python scaffold ships carry no prose. Where a file is the
twin of a root workflow, the reasoning above applies unchanged (`review_threads.yaml`,
`coderabbit_trigger.yaml`, `review_retry.yaml`, `pr-reconcile.yaml`, `secret_scan.yaml`).
This section records what is specific to the generated copies.

### `tests.yaml`

- **No `outputs:` on `workflow_call`.** It once declared `ready_for_release` as
  `${{ jobs.test.result == 'success' }}`. Only `jobs.<id>.outputs.<name>` is in scope there,
  so the output was an empty string on every run while looking like a release gate. It had no
  consumers; a caller reads the verdict from `needs.<job>.result`.
- **The job name carries every matrix axis.** With only `os` in it, the 3x5 matrix produced 15
  check runs sharing 3 names. A required check is resolved by name, so a green and a red leg
  of one name are indistinguishable to the merge gate.
- **`fetch-depth: 0`.** The work-ledger gate resolves `merge-base(HEAD, default)`, which a
  shallow clone cannot find; the gate-integrity gate diffs against `main` for the same reason.
- **The lockfile check is an unconditional step before the pyproject rewrite.** Nested under
  the install's `if: cache-hit != 'true'` it never ran on a warm cache, which is exactly the
  condition that makes it cheap. A stale `poetry.lock` fails loud: regenerating would
  re-resolve every dependency to the newest in-range version, a non-reproducible build. A
  version bump does not invalidate the lock, so `poe bump_version` never trips it.
- **The cache holds `.venv` only, keyed on `poetry.lock` and `pyproject.toml`.** Caching the
  tracked lockfile lets a restored cache overwrite the committed one. Hashing `pyproject.toml`
  alone makes the lock-only diff Dependabot's `lockfile-only` produces a cache hit, so every
  bump PR would skip the install and test the pre-bump set.
- **Every gate is an explicit step as well as a pre-commit hook.** CI does not run
  pre-commit, so a gate listed only there is bypassed by a contributor who skips hooks;
  `check-sql-guards` shipped one-legged that way and a `WHERE`-less `DELETE` reached `main`
  (#355). Per-gate points:
    - `lint-deps` runs inside the Poetry venv and cannot become `pipx run deptry`: deptry maps a
      module to its distribution through the environment it runs in, and outside it the verdict
      inverts rather than degrades.
    - `check-comment-language` runs in audit mode (no filenames), sweeping every commented file
      type, because a partial sweep leaves a precedent the next author copies.
    - `function-length`, `fixture-scope`, `check-complexity` and `identifier-masking` fail when
      discovery matches zero files. `check-complexity` hard-fails when ruff cannot be resolved.
    - `gate-integrity` is diff-scoped (#309): a PR may not weaken a hook, rule, exclude or check
      without a `gate-change-ok: <reason>` marker.
    - `coverage-floor` exits 0 with a message on a tier with no `src/capabilities/` (MVC) and
      `migration-graph` self-skips on a tier with no `migrations/versions/`.
    - `fixture-scope` is a proxy, not a detector (#442); see the gate's module docstring.
    - The others pin one invariant each: `check-typing` (every `src/` class or function carries
      the runtime checker, Pydantic models excepted), `check-provenance` (a module that calls
      `read_table` also calls `stamp_provenance`), `check-all-exports` (a declared `__all__`
      names every public member, which an introspective test that discovers the family through
      `__all__` cannot catch), `check-dtypes` (no ingested column typed as a binary float, which
      stores 1984223115.42 as 1984223115.4200000762939453125), `check-layer-imports` (a
      third-party dependency is reached through a `utils/` seam, in any scope),
      `check-orm-model-guards` (#361: bitwise operators in `.where()`, two `create_all`, and a
      duplicate constraint `name=` across a mixin MRO, each a silent wrong answer at
      declaration time), `specs-structure` (a tree with no `.specs/` passes, a malformed one
      fails by name), `check-docs-sections`, `check-docs-code-refs` (#159) and
      `check-backlog-ledger`.
- **Pinning pins what is asked for, never what arrives.** `gitleaks` and `actionlint` are
  unpacked and executed on the runner, so each download is SHA-256 verified before
  extraction. `LINT_ACTIONS_REQUIRED=1` turns actionlint's graceful skip into a failure: the
  skip is right on a contributor's machine and a placebo in CI.
- **`ruff format` is a CI step** so unformatted code fails, not only lint findings. mypy runs
  from `src/`, the single package base, to avoid the "found twice" error on the deeper DDD
  tree. shellcheck and shfmt are installed so the shell gate runs instead of skipping.
- **`|| [ $? -eq 5 ]` on the integration run.** Pytest exit 5 means no tests collected, which
  a fresh project's empty suite must not turn into a red CI; exit 1 still fails.
- **The coverage floor runs on every PR.** The badge step runs only on main and tags, so
  without the floor step a PR could drop coverage uncaught. The badge uses `--local` because
  the default form fetches from img.shields.io, and no CI or release path may depend on a
  non-essential external host.

### Other generated workflows

- **`pr-gate.yaml`.** It triggers on `pull_request` only, never `workflow_run`, which fires
  only from the default branch's copy and so cannot run on the PR that introduces the gate.
  The gate polls the checks in-run instead. `labeled` and `unlabeled` are included so
  `do-not-merge` takes effect at once. A pull_request-driven gate never re-evaluates an
  already-open PR after a policy change; run the `workflow_dispatch` with `backfill: true`
  (or `@dependabot rebase`) to re-decide every open PR. A new push cancels the previous
  polling run so two gates do not race on one sticky comment. Event data reaches the script
  through `env:` only.
- **`release.yaml`.** A service is deployed, not published, so there is no PyPI step. The
  version input is free text and is validated before `git tag`, the irreversible half. The
  versioned-docs job runs only after the tag is cut, so the site never advertises a version
  that failed to ship. `mike` deploys `X.Y` under the `latest` alias; a prerelease suffix
  is skipped in-step so it never moves `latest`. The dropdown granularity is `X.Y`, so 1.4.2
  and 1.4.7 share an entry. `CHANGELOG.md` is regenerated by `cz` for that build and not
  committed back to protected `main`. GitHub Pages must serve from `gh-pages`
  (`poe enable_pages`).
- **`contract_drift.yaml`.** A weekly, non-gating reporter on `schedule` and manual dispatch,
  never `pull_request` or `push`, so it cannot gate a PR or a release. It opens or updates
  one deduplicated issue and never fails the run; it is inert until a source is added to
  `src/config/contract_oracles.yaml`. Dedupe is on the `contract-drift` label and a hidden
  body marker, since the label alone can be removed by hand and a job that files an issue per
  run gets switched off. The report goes in as `--body-file` so source-derived text cannot
  inject into a shell command.
- **`review_threads.yaml`.** `actions: write` is for the stale-run cleanup only. Set
  `REVIEW_THREADS_REQUIRE_RESOLVED` to `0` for a reply-only contract; the shipped value is `1`.
  `bin/enable_repo_rules.sh` seeds `REQUIRED_CHECKS` with this job's `name:`.
- **`coderabbit_trigger.yaml`.** The scaffolder sets `GH_PAT_REVIEW_TRIGGER` when it is exported
  at scaffold time and prints the command otherwise. Scope the PAT to all repositories if you
  scaffold often, since a per-repository PAT is edited for every new project. It ships with
  the review-thread gate: without the gate this workflow is a nicety, without the workflow
  the gate blocks every PR.
- **`secret_scan.yaml`.** It is opt-in (#287): copied only when `GITGUARDIAN_API_KEY` is set at
  scaffold time, the same presence check that propagates the key to the new repo's secrets.
  It is not in `REQUIRED_CHECKS`, since a required check that never reports blocks every PR.
  An absent key fails loud, never skips: ggshield exits 3, distinct from a clean exit 0.
- **`review_retry.yaml`.** GitHub disables a scheduled workflow after 60 days of repository
  inactivity without announcing it. If rate-limited PRs stop being re-asked, check that the
  workflow is still enabled before looking for a bug in the script.
- **`pr-reconcile.yaml`.** Cards in a Projects "closed to Done" automation key on the issue
  closing, so a missed close leaves them in "In review" while the code has shipped, and the
  problem grows with auto-merge adoption. The workflow calls `bin/pr_reconcile.sh`, the one
  implementation shared with the root workflow. On the event path it reconciles that PR; on
  `schedule` and dispatch it sweeps a window.

### `dependabot.yml`

- **Ordinary version updates only.** Security updates are a repository toggle
  (`poe enable_security`), not config.
- **`versioning-strategy: lockfile-only`.** CI installs from the committed lock and refuses to
  re-lock, so it tests the frozen versions while consumers get whatever the loose `>=` ranges
  allow. This refreshes the lock but never rewrites pyproject ranges: narrowing a library's
  range on a consumer's behalf is not the project's call, and pyproject and lock stay in sync.
- **Solo-maintainer tuning.** Minor and patch are grouped into one PR; majors arrive alone and
  get scrutiny. Each PR (one grouped minor-and-patch update, or one major) is isolated, so a bad bump reddens that PR and never `main`. A
  linter bump (ruff, mypy) can ask for a reformat, which is the system working.
- **No `labels:` key**, because `bin/pr_gate.py` already labels by changed path and Dependabot
  comments an error on every PR it opens when a declared label does not exist. When a scaffold
  ships both a bot config and a labelling gate, only one may own labels.
- **Major-line pins** go for dependencies whose major is a support decision. pandas is tested on
  both 2.x and 3.x, so its major bump is a project decision. Add one per such dependency and
  remove it when the project stops straddling.
- **The Actions ecosystem entry** keeps CI off deprecated runtimes, for example a Node version
  GitHub is sunsetting.
