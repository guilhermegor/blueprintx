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
- [ ] Root of the majority (8 of 20): the `except ImportError: <driver> = None` fallback,
      copied across all six handlers — fixing the shape once fixes most of them
- [ ] Type the DSN parsing and the `pg_dump` / `mysqldump` argv builders (`list[str]`)
- [ ] Drop `[mypy-chassis.*] ignore_errors` and the `^chassis/` exclude once the tree is clean
- [ ] Audit the remaining `exclude` entries for the same import-reachability hole
      (`capabilities/example_feature/` is the obvious next one)

## #189 — function-length gate (60 lines, docstring excluded)

- [x] Decided 2026-08-20: **route 2** — Python and shell in the same PR, including the
      `copy_common_templates` duplication across the 5 scaffolds
- [ ] `bin/check_function_length.py` on `ast` (Ruff has no per-function line-count rule;
      `PLR0915` counts statements, a different metric)
- [ ] Wire into all 4 surfaces on both sides (pre-commit, CI, `Makefile`, `tasks.sh`)
- [ ] Fail when discovery matches zero files; print the count on success
- [ ] Negative control + an entry in the 5 hand-maintained copy lists
- [ ] Refactor the ~13 shell functions over the ceiling, largest first
      (`pip_fallback_emit_pip_requirements_from_pyproject` at 155 lines)

## Note

#167 (cyclomatic complexity) **does exist as an open issue** — what does not exist is an
implementation. The readiness checkpoint in memory claimed there was no issue either; corrected
here.

## Found during this session

- **#201** (open) — a template unit test invokes the real `gh` binary and the live network.
  Surfaced by the `act` verification on the #192 branch; deliberately not bundled into it.
- Lessons captured in the global store: `every-ci-job-needs-a-timeout.md` (updated with the
  implementation numbers and the act-image probe) and
  `unit-tests-must-not-reach-real-binaries.md` (new, backing #201).
