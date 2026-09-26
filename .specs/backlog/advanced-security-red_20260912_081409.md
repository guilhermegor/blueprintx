# `github-advanced-security` red on every PR — re-confirmation round (blueprintx#221)

Tracks the 2026-09-12 re-confirmation of blueprintx#221. The full investigation,
including the proof that this check does **not** block merges and the "document,
don't silence" decision, already lives in
`docs/backlog/pr-gate-blocks-merge_20260817_104500.md` (section
`## github-advanced-security (#221) — final decision: document, don't silence`).
This file is a dated log entry for this round only — it does not restate that
record, it re-measures against it.

## What was re-confirmed today

- [x] **Reproduced on a live PR.** `gh pr view 458 --json statusCheckRollup` does
      **not** list `github-advanced-security` by that route (GraphQL
      `statusCheckRollup` omits it) — it only surfaces via the REST check-runs
      endpoint:
      `gh api repos/guilhermegor/blueprintx/commits/<head-sha>/check-runs`.
      There, `github-advanced-security` (app slug `github-actions`) reports
      `conclusion: failure`, `title: null`, `summary: null` — same signature as
      every prior measurement.
- [x] **Read the actual failure from a real run**, not the issue title:
      `gh run view 34688212652 --log-failed` on job `103538833650` (PR #458,
      commit `96ecb7f`) shows:
      ```text
      COPILOT_AGENT_MODEL: sweagent-capi:claude-opus-5[ReasoningEffort=medium]
      Error creating PR review request: SessionModelError: Execution failed:
        CAPIError: 400 The requested model is not supported.
      autofind.js version: 0.1.130
      ```
      The model name has moved again — `claude-opus-4.6` (2026-08-22/28) →
      `claude-opus-5[ReasoningEffort=medium]` (2026-09-12) — and `autofind.js`
      bumped `0.1.117` → `0.1.130`. The 400 survives both. This is the third
      measurement across three weeks showing the same defect through two agent
      redeploys and one model-name change on GitHub's side.
- [x] **Confirmed (again) this is a repo setting, not a workflow file.**
      `templates/python-common/bin/enable_repo_rules.sh::enable_code_scanning`
      only PATCHes `code-scanning/default-setup` (the CodeQL config), which has
      no Copilot Autofix field — matching the prior finding that no
      REST/GraphQL endpoint exists for the Autofix toggle. The workflow is still
      GitHub-generated and dynamic (absent from `.github/workflows/`), so there
      is no YAML in this repo to edit.

## Consequence

No code change is available. Per the standing decision, this file documents the
re-confirmation and defers the lever to whoever holds repo-admin: **Settings →
Code security → Copilot Autofix → Disable.** Still not urgent (the check does
not block merges, proven in blueprintx#173), still recommended, still an owner
action — not something a PR in this repo can execute.

- [x] Re-measured 2026-09-12 (PR #458, commit `96ecb7f`) — no drift from the
      2026-08-22/2026-08-28 findings beyond the model name and `autofind.js`
      version, both cosmetic to the root cause.
- [ ] Owner decision pending: flip Settings → Code security → Copilot Autofix
      to Disabled (dashboard-only, no CLI/API path found across three attempts).

Completed for this round — kept as a record. Refs #221 (not `Closes #221`): the
check's color in the GitHub UI is unaffected by this PR, only the reproduction
evidence is refreshed.
