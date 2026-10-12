# Backlog — #192 (CI timeouts) · #190 (mypy chassis) · #189 (function-length gate)

Opened 2026-08-19, the three issues left open after section A of the duskko readiness work closed.

## #192 — unbounded apt-get hangs the scaffold jobs

- [x] Guard the `envsubst` install on `command -v` (2 occurrences,
      `.github/workflows/scaffold_checks.yml`)
- [x] Guard the `shellcheck` install the same way — same shape, same exposure
      (`scaffold_checks.yml`, `templates/python-common/.github/workflows/tests.yaml`)
- [x] `timeout-minutes` on **every** job with `runs-on:` — 22 workflow files, none had a bound
      (jobs that only `uses:` a reusable workflow cannot carry the field)
- [x] Verify under `act` that the install still runs where the tool is genuinely missing.
      Probed the image rather than assuming: **both `envsubst` and `shellcheck` are absent**
      from `catthehacker/ubuntu:act-latest`, and both install branches fired.
- [x] `bin/ci/check_actions.sh` green — and it grew `check_job_timeouts`, because applying the
      bound by hand fixes today's tree while the next workflow ships unbounded
- [x] **PR #202 open**, closing link verified through GraphQL → `192`. Final count:
      22 workflows / 43 runner jobs, wider than the 9-of-9 measured in the issue.

## #190 — chassis handlers outside the type check

mypy's `exclude` only filters discovery; `[mypy-chassis.*] ignore_errors = True` already landed
in #191. What remained was whether the debt becomes type-clean code.

- [x] Decided 2026-08-20: **type the handlers**. They are copied into every generated DDD
      project, so "reference scaffolding" is a claim about intent, not about who runs the code.
- [x] Root cause was narrower than the issue assumed: **14** of the 20 (not 8) descend from a
      single annotation, `_parse_dsn(...) -> dict[str, object]`. One shared `DsnParts`
      TypedDict in `chassis/db` fixed the DSN parsing, the `env[...]` assignments and the
      `pg_dump`/`mysqldump` argv builders in one move.
- [x] The other 6 were bare `# type: ignore` on the optional-driver imports, which silenced
      the `= None` fallback below them and were then reported as `unused-ignore`. Narrowed to
      `type: ignore[assignment]`.
- [x] Dropped `[mypy-chassis.*] ignore_errors` **and** the `^chassis/` exclude — the tree is
      type-clean, not silenced.
- [x] Audited the remaining excludes. `^capabilities/example_feature/` was excluded **and
      checked anyway** (`main.py` and `app/container.py` import it), so it was suppressing
      discovery of files the import graph pulled straight back in. Dropped it too: 58 → 69
      checked files, zero new errors.
- [x] Verified with `bin/ci/scaffold_lint_test.sh` on **all five** Python tiers, since
      `mypy.ini` is shared: ddd-native 33 → 69, ddd-orm 60, mvc-native 36, mvc-orm 35,
      lib-minimal 20 — `Success` on every one, 311/316/98 unit + 32 integration per tier.

### Deliberately not done in #190

- **No unit test for `_parse_dsn`.** The DDD tier ships no tests of its own (every test comes
  from `python-common/tests/`, which runs in MVC and lib tiers where the handler does not
  exist), so a tier-local test has no copy mechanism today. The runnable check is mypy itself,
  proven in both directions: 20 errors before, 0 after.
- **ruff still excludes `src/chassis`.** mypy and ruff no longer agree, which is a real
  divergence and not drift — filed as **#203** with the measurement to run first, rather than
  silently widening this PR into a ~1300-line style cleanup.

## #189 — function-length gate (60 lines, docstring excluded)

- [x] Decided 2026-08-20: **route 2** — Python and shell in the same PR, including the
      `copy_common_templates` duplication across the 5 scaffolds
- [x] `bin/check_function_length.py` on `ast`. Reproduces the issue's three Python numbers
      exactly (69/68/65), which is the agreement that pins the metric per #167. Shell is
      measured at the same single ceiling, exactly rather than heuristically, because
      `shfmt` guarantees the `name() {` / column-0 `}` shape.
- [x] Fails on zero discovery; prints the file count on success.
- [x] `--root`, so BlueprintX runs the template's file over its own tree instead of keeping
      a second copy that would drift.
- [x] The real count is **20**, not the ~13 in the issue — and 11 of those were two
      duplicated families. ⚠️ It read 21 until review caught a defect in the metric: only a
      function's OWN docstring was subtracted, so a decorator factory was charged for its
      closures' NumPy sections. `retry_with_backoff` was the single false positive and is
      reverted to byte-identical with `origin/main`.
- [x] `copy_common_templates` ×4: the copies differed by **one token**. Now one lib split by
      destination concern. 380 lines → 24. Proven byte-identical against `origin/main`.
- [x] `prompt_git_remote_setup` ×6: 391 lines → 35, and it surfaced two real defects
      (see below).
- [x] **20 → 0.** `check_function_length.py --root .` now reports
      `function length OK (276 file(s) checked)`.
- [x] Wired into all 4 surfaces on **both** sides — but with ONE implementation, not two:
      BlueprintX runs the template's file over its own tree via `--root .`. A second copy is
      exactly what `check_codespell_sync.sh` exists to police.
- [x] Negative control: `tests/unit/test_function_length_gate.py`, 9 tests, including "a
      function over the ceiling IS reported", "a long docstring does NOT count", and "audit
      mode FAILS when discovery matches nothing". Added to the copy lists — the copy-list
      gate caught its absence in all 5 scaffolds first, which is what it is for (32 → 33).

### How the remaining 11 were resolved

Three were not really shell at all — they were heredocs, and the length was the symptom:

- `pip_fallback…` (155) and `build_union_ca_bundle` (73) wrapped 151 and 66 lines of Python
  that **no Python tool could see**. Now `bin/lib/pip_requirements.py` and
  `bin/lib/ca_bundle.py`; extraction cost 3 ruff findings on the first run.
- `show_help` (65) was 64 lines of help text — duplicated as ~65 `@echo` lines in the
  Makefile, which had **already drifted** (`make help` was missing `test_cov_report` and
  `test_cov_serve`). Both now read `bin/help.txt`.

The other eight were split by concern: `copy_common_templates`/`create_python_files` in
lib-minimal, `prompt_pages_setup`, `check_url`, `process_python_files`, `find_file_problems`,
`pr_gate.main`, `retry_with_backoff`.

### Decision recorded (2026-08-21)

The metric was NOT changed. The question came up because a 65-line `cat <<EOF` and a 155-line
embedded Python program counted the same — but the answer was to take the inert blob out of
the function and give it its own file, which is what the gate was asking for all along. Both
heredoc cases are now genuinely short, with no exception carved into the rule.

### Defects the dedupe surfaced (fixed here)

- **35 `print_status "warn"` calls** across the 5 Python scaffolds. The function accepts
  `warning`; `warn` fell through to the catch-all and printed an unmarked `[ ] message` —
  every one of them a warning that rendered exactly like ordinary output. The catch-all now
  names the bad status on stderr, so the next typo cannot hide the same way.
- **`push_done=1` inside a `( … )` subshell**, so the flag never reached the parent and the
  follow-up push always ran, in six scaffolds. ShellCheck had reported it all along as
  SC2030/SC2031 — at `info`, below the gate's `--severity=warning` floor. `check_shell.sh`
  now runs a second pass for exactly those two codes.
- **My own gate change broke `check_test_copy_lists.py` in the dangerous direction.** Making
  it follow `source` was necessary, but with one shared lib it over-reported reachability:
  lib-minimal sources the git-remote half without calling the Python copy functions, so four
  shared tests were claimed to reach a tier that never copies them. Fixed by splitting the
  lib in two so `source` means what the gate assumes.

## Note

`#167` (cyclomatic complexity) **does exist as an open issue** — what does not exist is an
implementation. The readiness checkpoint in memory claimed there was no issue either; corrected
here.

## Found during this session

- **#201** (open) — a template unit test invokes the real `gh` binary and the live network.
  Surfaced by the `act` verification on the #192 branch; deliberately not bundled into it.
- ~~**#207**~~ **(CLOSED 2026-08-23, PR #224, v0.15.11)** — `ruff.toml` NO LONGER excludes
  `"bin"`; the 73 findings behind it are at 0. ⚠️ The text below describes the state BEFORE
  that fix — kept as the record of why, not as a live to-do.
  ~~`ruff.toml` excludes `"bin"`, so the 16 Python files that ARE the~~
  project's quality machinery are neither linted nor type-checked; 58 findings behind it,
  including an unsafe YAML load and a banned API. Third instance of the #190/#203 shape and
  the largest. Found while checking whether the extracted heredocs were really being linted —
  they were not; I had named the paths explicitly.
- **#206** (open) — `check-urls` never scans a ONE-LINE docstring and reports "All docstring
  URLs are reachable". Measured: the same 404 URL passes on one line and fails across three.
  Found while splitting `process_python_files`; the split reproduces the blind spot exactly,
  verified end-to-end before and after, so the defect is pre-existing and untouched here.
- **#205** (open) — `cp -r` ships `templates/**/__pycache__` into generated projects.
  Found by the before/after tree diff used to prove the #189 dedupe changed nothing.
- **#203** (open) — ruff vs mypy now disagree about `src/chassis`. Surfaced by #190; the
  `mypy.ini` comment claiming the two lists mirrored each other had become false, so it was
  corrected rather than left to rot.
- Lessons captured in the global store: `every-ci-job-needs-a-timeout.md` (updated with the
  implementation numbers and the act-image probe) and
  `unit-tests-must-not-reach-real-binaries.md` (new, backing #201).

## Defects found by the refactors themselves

Every one of these was invisible until a long function was pulled apart:

1. **35 `print_status "warn"`** — the function takes `warning`; those 35 printed an unmarked
   `[ ] message`. Fixed, and the catch-all now names a bad status on stderr.
2. **`push_done=1` inside a subshell** in 6 scaffolds — the flag never reached the parent.
   ShellCheck had it all along as SC2030/SC2031, below the gate's `--severity=warning` floor.
3. **`envsubst` reads the ENVIRONMENT** — converting lib-minimal's heredocs produced the
   empty string for `${PROJECT_NAME}` (`version("")`, `from .main import main`), a broken
   package from a green scaffold run. Caught only by the before/after tree diff.
4. **My own gate change over-reported reachability** — teaching `check_test_copy_lists.py` to
   follow `source` was necessary but, with one shared lib, claimed four tests reached
   lib-minimal that nothing copies there. Fixed by splitting the lib in two.
5. **`make help` had drifted** from `./tasks.sh help`, missing two real targets.
6. **#206**, above — pre-existing, filed rather than folded in.

## Closed out 2026-08-22

All three issues delivered and merged: #192 (PR #202), #190 (PR #204), #189 (PR #209 + the
`#213` cleanup). Released as **v0.15.7** (#192 + #190) and **v0.15.8** (#189), each verified on
per-job conclusions, tag presence and non-draft state.

⚠️ **Two corrections to what this ledger claimed earlier**, kept visible rather than edited
away, because both are the more instructive half:

1. The gate's metric counted **nested** docstrings, so a decorator factory paid for its
   closures' documentation. That number made me shorten those docstrings — documentation
   deleted to satisfy a counter, which is the exact incentive the docstring exclusion exists
   to remove. Corrected; the tree's real count was 20, never 21.
2. A careless `cp` shipped a **second copy** of the gate at `bin/lib/`, in the PR arguing
   against duplication. It was already the stale copy. Removed in #213.

Nine issues opened from findings along the way: #201, #203, #205, #206, #207, #208, #211,
`#212`. Kept as a record per the backlog discipline — do not delete this file.
