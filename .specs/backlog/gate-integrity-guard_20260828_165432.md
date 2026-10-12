# Gate-integrity guard (#309, lever 1)

Owner-flagged priority. Detect a PR that removes or weakens a quality control (a pre-commit
hook, a ruff rule, an exclude path, a `bin/ci/` check, a workflow job, a required status
check, a `pytest.ini` escalation) without an explicit `gate-change-ok: <reason>` justification.
Levers 2 (semgrep, #305) and 3 (issue spec density) are explicitly out of scope here.

- [x] Read #309 in full; confirm scope is lever 1 only.
- [x] `templates/python-common/bin/check_gate_integrity.py` — one implementation, diff-scoped
      against `merge-base(HEAD, main)` (the deliberate departure from the whole-tree siblings).
- [x] Wire on BOTH sides: root `.pre-commit-config.yaml` + `.github/workflows/scaffold_checks.yml`
      (BlueprintX itself), and `templates/python-common/.pre-commit-config.yaml` +
      `.github/workflows/tests.yaml` (every generated project).
- [x] Fold should-fail-witness pure-logic tests into the existing copy-listed
      `templates/python-common/tests/unit/test_backlog_ledger.py` (no new test file, so no
      copy-list entry needed).
- [x] Verify: `check_complexity.sh --root templates/python-common`, `check_function_length.py`,
      `ruff check`/`ruff format --check`, `mypy`, `pytest` — all clean.
- [x] Three should-fail witnesses against a throwaway git repo: hook removed → fails naming the
      hook; same diff + `gate-change-ok:` trailer → passes; line-level `# noqa: E501` addition →
      passes (never dispatched — the gate only ever reads five config basenames).
- [x] Historical scan `origin/main~100..origin/main`: 10/100 commits would have been flagged, all
      legitimate (per-file-ignores additions, exclude additions, consolidation deletions) and each
      already carries prose in-repo that would satisfy a one-line justification. Found and fixed a
      real bug during the scan: a quoted phrase inside a `ruff.toml` comment was misread as a rule
      code (`strip_toml_comments`).
- [ ] `bash bin/ci/scaffold_lint_test.sh <tier>` in the foreground (at least one tier).
- [ ] Open PR, watch CI, resolve any review threads, merge on green gates.

Completed — kept as a record once every box above is ticked.
