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
- [x] Write `templates/python-common/bin/check_comment_budget.py` — ONE
      implementation, `--root .` support.
- [x] Write the anticipatory allowlist data file
      (`templates/python-common/bin/comment_budget_allowlist.txt`).
- [x] Two distinct defect classes: long-run (essay block, ratchet ceiling) and
      decorative banner (regex-decidable, always a defect).
- [x] Escape hatch `# comment-budget-ok: <reason>`, reason required.
- [x] Extensionless `Makefile` / `*.mk` handled by filename, not just suffix.
- [x] Structural exemptions: shebang, encoding declaration, SPDX header,
      generated-file banner markers — via the same allowlist mechanism.
- [x] Calibrate against the real tree; record finding counts + false-positive
      rate in the PR body.
- [x] Fix the small, mechanically-decidable banner violations found in BlueprintX's
      own tree (56 lines, 15 files) so the gate ships green — NOT the full #304 sweep.
- [x] Unit tests with named cases + a negative control
      (`templates/python-common/tests/unit/test_comment_budget_gate.py`, 23 tests).
- [x] Wire the new test into all 5 Python scaffolds' copy lists (caught by
      `check_test_copy_lists.py` — a gate this branch did not expect to need).
- [x] Wire: template `.pre-commit-config.yaml`, `poe_tasks.toml`, `bin/lint.sh`.
- [x] Wire: BlueprintX's own `.pre-commit-config.yaml` (`--root .`).
- [x] Wire: `.github/workflows/scaffold_checks.yml` — own commit (held file),
      done by the coordinator with `--no-verify`, re-verified by re-running the
      full hook set after the fact (all pass, including the new hook itself).
- [x] Update `CLAUDE.md` — the deptry passage the issue quotes now says
      explicitly that its inline reason is short (2-4 lines, measured against
      all 5 manifests) and distinct from the long-essay case #303 targets.
      `templates/python-common/CLAUDE.md` had no contradicting passage.
- [ ] `docs/blueprintx-lessons.md` status update — SKIPPED, not applicable:
      the file is git-ignored (`.codespellrc`'s own comment confirms it — "the
      git-ignored mirror the lessons-capture workflow writes"), so it is not
      part of this PR's diff and has nothing to commit.
- [ ] Run `bin/ci/scaffold_lint_test.sh <tier>` for at least one tier.
- [ ] Open PR, `Closes #303`.

Session-limit note: killed once holding 2 uncommitted files (the gate fix +
23-test suite); coordinator committed them with `--no-verify` and pushed.
Resumed 2026-09-12: rebased onto main (#437 ruff RET family, #450 ts-common
fix), re-ran the full hook set (all pass), verified the banner-deletion commit
removed zero QA suppressions (`git show <sha> | grep '^-' | grep -iE
'noqa|codespell:ignore|complexity-ok|type: ?ignore|lang:pt-ok|...'` — no
matches), and fixed the copy-list gap found by `check_test_copy_lists.py`.
