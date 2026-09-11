# Comment-budget gate (blueprintx#303)

Tracks implementation of the comment-budget gate: bound comment volume in every
code format, QA suppression pragmas explicitly exempt. Sibling issue #304 (the
cleanup sweep) is explicitly OUT of scope for this branch — it collides with
PR #424 (100 files held).

## Checklist

- [x] Re-verify the gate does not already exist (`check_comment_language.py` is a
      different gate; `comment_budget` greps clean except the tracking lesson).
- [x] Read `check_comment_language.py` as the structural model (block extraction,
      `--root`, zero-discovery failure, file-count-on-success).
- [ ] Write `templates/python-common/bin/check_comment_budget.py` — ONE
      implementation, `--root .` support.
- [ ] Write the anticipatory allowlist data file
      (`templates/python-common/bin/comment_budget_allowlist.txt`).
- [ ] Two distinct defect classes: long-run (essay block, ratchet ceiling) and
      decorative banner (regex-decidable, always a defect).
- [ ] Escape hatch `# comment-budget-ok: <reason>`, reason required.
- [ ] Extensionless `Makefile` / `*.mk` handled by filename, not just suffix.
- [ ] Structural exemptions: shebang, encoding declaration, SPDX header,
      generated-file banner markers — via the same allowlist mechanism.
- [ ] Calibrate against the real tree; record finding counts + false-positive
      rate in the PR body.
- [ ] Fix the small, mechanically-decidable banner violations found in BlueprintX's
      own tree (Makefile) so the gate ships green — NOT the full #304 sweep.
- [ ] Unit tests with named cases + a negative control
      (`templates/python-common/tests/unit/test_comment_budget_gate.py`).
- [ ] Wire: template `.pre-commit-config.yaml`, `poe_tasks.toml`.
- [ ] Wire: BlueprintX's own `.pre-commit-config.yaml` (`--root .`).
- [ ] Wire: `.github/workflows/scaffold_checks.yml` — own final commit (held file).
- [ ] Update `CLAUDE.md` + `templates/python-common/CLAUDE.md` — delete the
      superseded "reason lives inline" guidance that contradicts this gate.
- [ ] Update the tracked lesson (`docs/blueprintx-lessons.md`) status to delivered.
- [ ] Run `bin/ci/scaffold_lint_test.sh <tier>` for at least one tier.
- [ ] Open PR, `Closes #303`.
