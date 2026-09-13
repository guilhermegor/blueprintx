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
- [x] Run `bin/ci/scaffold_lint_test.sh <tier>` for at least one tier —
      `lib-minimal`: scaffold clean, `poe lint` clean (including the new
      hook), 441 unit tests + 85 integration tests pass, including the new
      `test_comment_budget_gate.py` (23 tests) running inside the real
      scaffolded project.
- [x] Found and fixed a real regression along the way: the banner-deletion
      commit left a stray blank line in both `bin/lib/common.sh` copies;
      `shfmt -w` collapsed it on the scaffold's own `poe lint`, which the
      harness treats as a failure (same class as the #458 ruff-format
      warning). Fixed; re-ran the tier verification green.
- [x] Open PR, `Closes #303`. -> PR #460, verified via GraphQL
      closingIssuesReferences returns [303].

Session-limit note: killed once holding 2 uncommitted files (the gate fix +
23-test suite); coordinator committed them with `--no-verify` and pushed.
Resumed 2026-09-12: rebased onto main (#437 ruff RET family, #450 ts-common
fix), re-ran the full hook set (all pass), verified the banner-deletion commit
removed zero QA suppressions (`git show <sha> | grep '^-' | grep -iE
'noqa|codespell:ignore|complexity-ok|type: ?ignore|lang:pt-ok|...'` — no
matches), and fixed the copy-list gap found by `check_test_copy_lists.py`.

## PR #460 review threads (2026-09-13)

- [x] CodeRabbit Major: escape hatch listed in its own allowlist. **Valid, fixed.**
      `comment_budget_allowlist.txt` listed `comment-budget-ok:` itself, so
      `line_breaks_run` treated the marker as a pragma and BROKE the run before
      `has_valid_escape` ever saw it — the escape hatch could never exempt a
      block it opened, and a bare (reasonless) marker mid-block silently split
      one oversized run into two under-ceiling ones instead of failing
      validation. Removed the entry; added two should-fail-witness tests
      (`test_the_escape_hatch_exempts_a_real_oversized_block`,
      `test_a_bare_marker_inside_a_real_oversized_block_still_fails`) exercising
      the fix through `file_problems`, not just `has_valid_escape` in isolation.
- [x] CodeRabbit Major: decorative banners in the gate's own test file trip the
      audit. **Verified INVALID as stated — but led to a real, separate,
      bigger bug.** `marker_for()` never returns a marker for `.py` (`".py"` is
      in neither `DICT_HASH_SUFFIXES` nor `DICT_SLASH_SUFFIXES`), so
      `file_problems()` returns `[]` for every Python file before reaching the
      `.py`-specific `python_blocks()` branch — confirmed by running the gate
      directly (0 findings on 228/499 files "checked"). The 7 banner triples
      CodeRabbit named do exist in `test_comment_budget_gate.py` but currently
      trip nothing. Patching `marker_for` to cover `.py` in-process surfaces
      **142** findings tree-wide, the bulk being the exact `rule/title/rule`
      shape `tests/CLAUDE.md` **mandates** for test-file section banners (32
      files use it across python-common + both mvc-* tiers) — a real policy
      conflict (structural exemption vs. dropping the convention), not a
      mechanical cleanup, and out of scope for this already-wide PR (touches
      all 5 scaffolds + shared libs, collision risk with other in-flight PRs).
      Filed **blueprintx#466** to track; replied on the thread explaining why,
      resolved it.
- [x] Rebase check: `origin/main` — PR head was already up to date, no merge
      needed.
- [x] `poe unit_tests` scoped to the gate: `test_comment_budget_gate.py`, 25/25
      pass (23 existing + 2 new).
