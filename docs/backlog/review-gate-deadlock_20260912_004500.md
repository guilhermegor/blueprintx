# Review-gate deadlock (blueprintx#433)

A mass-formatting PR can never pass the review gate: `Review threads answered` is a required
check that correctly fails when no declared reviewer ran at all (blueprintx#213 hardening), but
CodeRabbit refuses to review any PR over its 100-file cap — so on a large PR, no reviewer ever
reports, and the required check can never go green. Confirmed live on PR #424 (2026-09-11):
notices at 238 then 241 files, each CI-fixing push making the PR *less* reviewable.

## Plan

- [x] Read blueprintx#433 and its live-reproduction comment; confirm the hard constraint (never
      treat a reviewer refusal as a pass — that reopens the #213 hole).
- [x] Read `templates/common/bin/check_review_threads.py` end to end; understand
      `find_missing_review_problem` / `classify_reviewer_notice` / the existing rate-limit
      classification pattern this fix extends.
- [x] Design the third state: a distinct FAILURE message (never a pass) that names the file cap
      and tells the author to split the PR. Rejected alternatives: an opt-out label (a
      collaborator could apply it speculatively, reopening #213 under a different door) and an
      early split-guard (prevents future PRs but doesn't discriminate the state the issue is
      about).
- [x] Implement: `NOTICE_FILE_CAP_EXCEEDED` classification (anchored on the vendor's full
      sentence, not the bare "Review skipped" prefix — a second, unrelated "Review skipped —
      Bot user detected" reason exists and must not be conflated), `_zero_review_message`
      helper extracted to keep `find_missing_review_problem` under the 60-line function-length
      ceiling.
- [x] Tests: reviewer ran clean → pass (unchanged); no reviewer at all → FAIL, #213 regression
      (unchanged, re-verified green); file-cap decline → FAIL with the new split-PR message;
      bot-detected decline → FAIL with the generic trigger-a-review message (proves no
      conflation between the two "Review skipped" reasons); reworded/absent notice → FAIL,
      never a pass.
- [x] Verify: `function-length`, `check-complexity`, `check-complexity-templates`,
      `gate-integrity`, `codespell`, `docs-code-refs`, and the full pytest suite for the gate
      (84 passed) — all green with hooks actually running (not `--no-verify`).
- [x] Commit + push at each coherent point (rescued once by the coordinator after a session-limit
      kill; committed and pushed twice more since).
- [x] Open the PR against `main` with `Closes #433`, following the PR template, arguing the
      three-option design choice in the body. PR #458 — verified via GraphQL
      `closingIssuesReferences` that it actually registers 433, not just links it.
- [ ] Confirm CI is green on the PR and address any review feedback.

Completed — kept as a record once every box above is ticked (CLAUDE.md backlog discipline).
