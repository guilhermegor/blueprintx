# Assertion-weakening gate (#324, companion to #309/#313)

Detect a PR that turns a red test green by weakening its assertion — the sharper half of
#309's gate-integrity guard, which watches config, not the assertion itself.

- [x] Read #324 in full.
- [x] **File-surface decision: new file, not an extension of `check_gate_integrity.py`.** The
      issue's stated preference is to extend that file, but it is held by open PR #330 in this
      same dispatch — editing it would collide. `templates/python-common/bin/check_assertion_weakening.py`
      duplicates a small slice of the sibling's git-diffing plumbing (`_git`/`show`/`changed_paths`/
      `default_branch`/`resolve_base`/`pr_body_text`/`apply_root_flag`) rather than importing it,
      since importing a sibling gate mid-flight under another open PR is a brittle dependency.
      The two files audit different questions (config weakening vs. assertion weakening), so this
      is not the drift `check_codespell_sync.sh` polices — but the duplicated plumbing should
      collapse into one shared module once #330 lands.
- [x] **Measured first, against real history**, per the issue's explicit working method:
  - `origin/main~100..origin/main` (100 commits), 39 touched `templates/python-common/tests/*.py`.
  - First draft ("either side of `==` changed, other unchanged" as the value-changed rule):
    **7/100 commits flagged, 17 findings** — one confirmed false positive (`test_retry.py`'s
    `dict_calls["n"] == 1` -> `cls_call.call_count == 1`, a rewritten LEFT side on an unchanged
    literal RHS, wrongly read as an edited expectation).
  - Narrowed the value-changed rule to require the CHANGED side be literal-ish (a constant, or a
    call/aggregate built only from constants — e.g. `Decimal("1.99")`, `date(2026, 6, 8)`) in BOTH
    versions, not merely "differs while the other side matches". Re-measured:
    **5/100 commits flagged, 6 findings** — better than #313's cited "payable" bar (11/100).
  - Of the 6: 4 are test/file deletions (by design always need a declaration — one is collateral
    from `tasks.sh` itself being deleted in the Poe migration, three are legitimate test removals
    during a redesign), 2 are value-changed findings (1 clear true positive — a login-normalisation
    behaviour change reflected in a test literal; 1 accepted borderline case — a helper renamed
    `add` -> `_add` on an unchanged RHS constant, still literal-ish on the LHS call by this rule's
    definition, resolved by the same one-line escape hatch). **Threshold used: "payable", not
    "zero violations"** (explicitly not conflating the two, per the issue's #168/PR #295 note).
- [x] Wrote `templates/python-common/bin/check_assertion_weakening.py` — AST-level, positional
      per-function comparison of a test file's merge-base version vs. the index. Rules: test/file
      deletion, assertion count decreased, trivialised to `assert True`, `==` weakened by operator
      (`in`/`not in`/`>=`/`<=`/`!=`), `assertEqual`-family call weakened (`assertTrue`,
      `assertIsNotNone`, `assertIn`, …), `pytest.raises` broadened or removed, a new
      `skip`/`xfail` marker, and the literal-ish-gated value-changed rule (only when a non-test
      file also changed in the same diff). Escape hatch: `test-change-ok: <reason>` in the PR body
      or a commit trailer, mirroring `gate-change-ok:`. Three states are distinct: flagged / clean /
      **could not parse** (a parse failure is its own finding, never silently clean).
- [x] Wrote `templates/python-common/tests/unit/test_assertion_weakening_gate.py` — 19 tests,
      offline (no git). Covers every rule firing on its named shape, the should-fail witness that
      a test-only correction with no production-code change must PASS (issue witness #3), the two
      measured-false-positive regression tests (rewritten LHS not read as a value edit; a
      count-preserving `raises` replacement still caught positionally), the three-state parse
      guard, and the escape-hatch trailer (present with a reason / absent / bare with no reason).
- [x] Added the copy line to `bin/lib/scaffold_python_templates.sh`'s `scaffold_copy_gate_tests`
      (the test file is NOT covered by the wholesale `bin/` directory copy — `tests/unit/` ships
      file-by-file). All five Python tiers route through `scaffold_copy_common_templates`, so one
      line covers all of them. The gate script itself needs no copy line: `scaffold_copy_executables_and_vscode`
      already does `cp -r "$COMMON_TEMPLATE_ROOT/bin/." "$str_project_path/bin"`.
- [ ] **Wiring deferred to a follow-up — option (b) from the dispatch brief.** `.pre-commit-config.yaml`
      (both root and `templates/python-common/`) and `.github/workflows/scaffold_checks.yml` /
      `templates/python-common/.github/workflows/tests.yaml` are held by open PR #330 in this same
      dispatch; touching them here would conflict with that PR's diff. **The gate does not run
      anywhere yet — this PR ships the detector, its tests, and the copy line only.** Follow-up
      (after #330 merges) needs four hook/CI entries, mirroring `check_gate_integrity.py`'s exact
      four wiring points: root `.pre-commit-config.yaml`, root `.github/workflows/scaffold_checks.yml`,
      `templates/python-common/.pre-commit-config.yaml`, `templates/python-common/.github/workflows/tests.yaml`.
- [x] Ran `ruff check --config templates/python-common/ruff.toml` and `ruff format --check` from
      inside `templates/python-common/` (not the root) — clean on both files.
- [x] Ran `pytest templates/python-common/tests/unit/test_assertion_weakening_gate.py` — 19 passed.
- [x] Should-fail witnesses in both directions, pasted in the PR body: operator weakening fires
      naming the line, a stricter operator swap stays clean; `assertEqual`->`assertTrue` fires; a
      value edit alongside production-code change fires, the same edit with no production-code
      change passes (witness #3); a bare `test-change-ok:` marker (no reason) does not justify.
- [ ] `bash bin/ci/scaffold_lint_test.sh <tier>` for at least two tiers — run before opening the PR.
- [ ] Open PR (branch `feat/assertion-weakening-gate-324`), body states the false-positive
      measurement and the wiring deferral explicitly, `Closes #324`. Watch CI, resolve review
      threads, merge on green gates.

Completed — kept as a record once every box above is ticked (wiring itself is a tracked
follow-up, not blocking this PR per the dispatch brief's option (b)).
