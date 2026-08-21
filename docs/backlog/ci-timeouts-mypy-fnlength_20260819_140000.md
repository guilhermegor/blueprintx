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
- [x] The real count is **21**, not the ~13 in the issue — and 11 of those were two
      duplicated families.
- [x] `copy_common_templates` ×4: the copies differed by **one token**. Now one lib split by
      destination concern. 380 lines → 24. Proven byte-identical against `origin/main`.
- [x] `prompt_git_remote_setup` ×6: 391 lines → 35, and it surfaced two real defects
      (see below).
- [ ] Remaining 11 over the ceiling: `copy_common_templates` in lib-minimal (127),
      `prompt_pages_setup` in ts_react_app (73), and 9 in python-common
      (`pip_fallback` 155, `process_python_files` 74, `build_union_ca_bundle` 73,
      `retry_with_backoff` 69, `find_file_problems` 68, `main` 65, `show_help` 65,
      `check_url` 63)
- [ ] Wire into all 4 surfaces on both sides (pre-commit, CI, `Makefile`, `tasks.sh`) —
      deliberately last: a gate that ships red is a gate someone disables
- [ ] Negative control + an entry in the copy lists

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

#167 (cyclomatic complexity) **does exist as an open issue** — what does not exist is an
implementation. The readiness checkpoint in memory claimed there was no issue either; corrected
here.

## Found during this session

- **#201** (open) — a template unit test invokes the real `gh` binary and the live network.
  Surfaced by the `act` verification on the #192 branch; deliberately not bundled into it.
- **#205** (open) — `cp -r` ships `templates/**/__pycache__` into generated projects.
  Found by the before/after tree diff used to prove the #189 dedupe changed nothing.
- **#203** (open) — ruff vs mypy now disagree about `src/chassis`. Surfaced by #190; the
  `mypy.ini` comment claiming the two lists mirrored each other had become false, so it was
  corrected rather than left to rot.
- Lessons captured in the global store: `every-ci-job-needs-a-timeout.md` (updated with the
  implementation numbers and the act-image probe) and
  `unit-tests-must-not-reach-real-binaries.md` (new, backing #201).
