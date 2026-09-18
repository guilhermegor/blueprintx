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

## blueprintx#466 — the gate never actually checked .py files (2026-09-13)

Branch `fix/comment-budget-gate-checks-py-466`, off `origin/main` (which already
carries the PR #460 review-thread fix above via squash-merge, commit `8c00d15`).

- [x] Root cause confirmed: `marker_for()` recognized only
      `DICT_HASH_SUFFIXES`/`DICT_SLASH_SUFFIXES`, neither of which lists `.py` —
      `file_problems()` returned `[]` for every Python file before ever reaching
      the `.py`-specific `python_blocks()` branch. Fixed: `marker_for` now
      returns `"#"` for `.py` explicitly.
- [x] Re-measured against the whole tree with the fix applied: 501 files
      genuinely checked (was 499 merely counted, 0 ever inspected), surfacing
      **144** real findings. All resolved, gate now reports
      `✅ comment budget OK (501 file(s) checked)`.
- [x] **The banner-policy decision, made explicitly** (gate and
      `tests/CLAUDE.md` must agree): **exempted**, not dropped — 128 of the 144
      findings were exactly this convention, measured to occur NOWHERE else in
      the tree (272 occurrences, always this one shape, only in `.py` files).
      Unlike a Makefile's rule/title/rule restating the ONE block beneath it,
      this title names a GROUP of tests, so it is not "documentation in
      disguise" — ripping it out of 31 files would have meant rewriting
      `tests/CLAUDE.md` too, for no functional gain.
- [x] **First mechanism was wrong — caught in review, fixed (2026-09-13,
      PR #479).** Initially implemented the exemption by adding the 26-dash
      string to `comment_budget_allowlist.txt`. That file is read by
      `is_pragma_line`, and `line_breaks_run` makes a pragma BREAK the current
      comment run — correct for a QA suppression, but it reopened the exact
      #460 thread-1 defect through a new door: one dash line inside an
      oversized block split it into two under-ceiling halves. Reproduced
      against the pushed head: 89 lines with no dash → 1 finding; 44 + one
      dash line + 44 → `✅ comment budget OK`. Fixed by reverting the
      allowlist entry and matching the exemption structurally instead:
      `STR_TEST_SECTION_RULE` + `is_exempt_section_banner` in
      `check_comment_budget.py` itself, checked inside `banner_findings` —
      the two rule lines stay in the block (still counted toward
      `INT_MAX_RUN`, still able to end a run at the ratchet) and only the
      TRIPLE finding is suppressed, matched on the full triple (not any line
      of 26 dashes), so a lone rule line elsewhere gets no special treatment.
      Re-measured after the fix: still 501 files, 0 findings (no real
      oversized block had been hiding behind a dash line in this tree). Added
      3 more should-fail witnesses: 44+dash+44 → finding (both a long-run AND
      a lone-banner finding, since the dash no longer breaks the run and isn't
      part of a clean triple), a full triple wrapped in an oversized block →
      still a long-run finding (banner suppressed, length not), and
      `is_exempt_section_banner` matches the full triple only.
- [x] Remaining 16 findings, two distinct real defects found along the way:
      4 were section titles quoting a gate marker's own name in backticks
      (`` `# complexity-ok:` ``), which `is_pragma_line`'s substring match
      misread as an actual pragma use and split the triple — reworded the two
      title lines to drop the literal marker text (`test_comment_budget_gate.py`,
      `test_rmw_race_gate.py`). The other 12 were genuine ad-hoc
      dash-wrapped rationale paragraphs (not the CLAUDE.md convention) in
      `test_bin_scripts.py`, `test_backlog_ledger.py`, `test_gate_integrity_gate.py`
      — deleted the decorative divider lines, kept the prose, same fix PR #460
      already applied to every other file type.
- [x] Added 4 should-fail witnesses: `.py` banner defect now caught, `.py`
      long-run defect now caught, the mandated section-banner shape stays
      exempt end-to-end via `file_problems`, `marker_for(".py") == "#"`.
      `test_comment_budget_gate.py`: 25 → 29 → **32** (the mechanism-fix round
      above added 3 more); 131 passed across the 4 touched test modules; full
      `python-common` gate: 501 files, 0 findings.
- [x] Real verification: `bin/ci/scaffold_lint_test.sh lib-minimal` —
      scaffold clean, `poe lint` clean (comment-budget hook included),
      458 unit tests + 85 integration tests pass in the real generated project.
- [x] Session-limit note: killed mid-task holding 7 uncommitted files;
      coordinator rescued via `git add -A` (staged, not committed) and a
      byte-exact backup patch. Resumed, verified the staged diff matched intent,
      committed (`273808e`, gitlint required a body-line rewrap first), pushed.
- [x] Opened PR #479, `Closes #466` verified via GraphQL
      `closingIssuesReferences` returns `[466]`.
- [x] Team-lead caught the split-run bypass in review before merge (see
      above) — auto-merge disarmed, PR converted to DRAFT so the hold could
      not be undone by accident (a bare disarm reads as residue to the
      standing "PR without auto-merge → arm it" sweep rule). Mechanism fixed,
      re-verified (32 tests, 501 files/0 findings, `scaffold_lint_test.sh
      lib-minimal` green) — ready to un-draft and re-arm.
