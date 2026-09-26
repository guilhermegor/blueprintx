# Dehydrate the .git/ PR/issue bodies — audit record (#584)

## Why this file exists

blueprintx#584 asked for the 31 (at filing time) markdown bodies sitting in
`<repo>/.git/` — written there because `pr_template_guard.sh` refuses a
`--body-file` outside the project directory, and `.git/` is the only path
that is *inside the repo* yet *never committed* — to be inventoried,
classified, and the **orphaned** ones filed under `.specs/features/`.

The inventory ran against the **main checkout's** `.git/` (not this
worktree's own), on 2026-09-21. It found **37** files, not 31 — the count
grew between when the issue was filed and when this audit ran, because
several sibling agents in the same dispatch round were actively opening
PRs for exactly the issues these bodies describe. **Every one of the 37
matched an issue or PR that already exists on the forge.** Zero were
orphaned, so nothing was filed under a feature directory as a `pr.md` —
this file is the permanent record of that finding, kept per this repo's
own rule that a completed audit is a record, not scratch to delete.

## Method

1. `rtk proxy find .git -maxdepth 1 \( -name "*.md" -o -name "msg*.txt" \)`
   over the main checkout's `.git/` (never the worktree's).
   `.git/pr-bodies/` exists but is empty (confirmed via `rtk proxy ls`, not
   inferred from a filtered listing).
2. Read every file's full content.
3. Fetched `gh pr list --state all --limit 400 --json number,title,headRefName`
   and `gh issue list --state all --limit 400 --json number,title` once each
   (two calls, not one per file) and matched by **content**, never by
   filename — the naming variants (`pr<N>.md`, `prA.md`, `issue_<topic>.md`,
   `msg<N>.txt`) do not reliably encode which issue/PR a file belongs to.
   Three matches were spot-verified by diffing the local file against the
   live `gh issue view` / `gh pr view` body (issue #583, PR #589, PR #581) —
   line counts and content matched exactly in all three, which is the basis
   for trusting the same content-match method on the rest.

## Inventory and verdict

| file | verdict | matches |
|---|---|---|
| `b507.md` | shipped | issue #507 |
| `b540.md` | shipped | issue #540 |
| `b544.md` | shipped | issue #544 |
| `c424.md` | shipped | PR #424 (comment; PR now CLOSED) |
| `close424.md` | shipped | PR #424 (closing comment; PR now CLOSED) |
| `issue_claudemd.md` | shipped | issue #549 |
| `issue_dehydrate.md` | shipped | issue #584 (this issue) |
| `issue_filecount.md` | shipped | issue #551 |
| `issue_open_trigger.md` | shipped | issue #567 |
| `issue_relver.md` | shipped | issue #548 (PR #557 merged) |
| `issue_rmw.md` | shipped | issue #561 (PR #566 merged) |
| `issue_scaffold_boundary.md` | shipped | issue #576 (PR #582 open) |
| `issue_spec_mode.md` | shipped | issue #481 (PR #525 open) |
| `issue_specs_guard.md` | shipped | issue #583 — verified by diff against `gh issue view 583`, exact match |
| `issue_tracker_move.md` | shipped | issue #575 (PR #580 open) |
| `msg434.txt` | superseded | draft 1 of the #434 rescue commit message, replaced by `msg434d.txt` |
| `msg434b.txt` | superseded | draft 2 of the same rescue, replaced by `msg434d.txt` |
| `msg434c.txt` | superseded | draft 3 of the same rescue, replaced by `msg434d.txt` |
| `msg434d.txt` | shipped | PR #562 (closes #434) |
| `msg521.txt` | shipped | PR #522 (docs fixup on the #169 blind-spots audit — filename is misleading, content is not about #521) |
| `msg522.txt` | shipped | PR #521 (bash-cli review-finding fixes, closes #518 — filename is misleading, content is not about #522) |
| `msg531.txt` | shipped | PR #531 (offline wheelhouse, #299) |
| `msg532.txt` | shipped | PR #532 (API service skeleton review findings) |
| `pr240.md` | shipped | PR #316 (closes #240) |
| `pr325.md` | shipped | PR #569 (closes #325) |
| `pr355.md` | shipped | PR #574 (closes #355) |
| `pr434.md` | shipped | PR #562 (closes #434) |
| `pr445.md` | shipped | PR #579 (closes #445) |
| `pr539.md` | shipped | PR #550 (closes #539; PR itself still a partial draft, but the PR exists) |
| `pr544.md` | shipped | PR #581 — verified by diff against `gh pr view 581`, exact match |
| `pr549.md` | shipped | PR #573 (closes #549) |
| `prA.md` | shipped | PR #552 (1/4 of the #424 split) |
| `prB.md` | shipped | PR #553 (2/4 of the #424 split) |
| `pr_cb.md` | shipped | PR #547 (comment-budget fix) |
| `prC.md` | shipped | PR #554 (3/4 of the #424 split) |
| `prD.md` | shipped | PR #555 (4/4 of the #424 split) |
| `pr_lockfile_sync.md` | shipped | PR #589 — verified by diff against `gh pr view 589`, exact match |

**Totals: 34 shipped, 3 superseded, 0 orphaned, 0 UNKNOWN.**

## What this means for the migration

Because nothing was orphaned, nothing was filed as `.specs/features/<name>/pr.md`
on this pass. The `pr.md` convention itself (dotfiles-dev#441) is unaffected
by this finding — it still applies the next time a body is genuinely
unopened. blueprintx#583 owns building the guard that keeps future bodies
from accumulating unfiled; this issue was scoped to migrate what already
existed, and what already existed had already reached the forge by the
time the migration ran.

## Ownership boundary

All 37 files reference blueprintx issue/PR numbers and matched entries in
this repo's own issue/PR lists. None referenced a dotfiles-dev issue as
their own subject (dotfiles-dev numbers appear only as "Related:" links
inside a few bodies) — so none needed to be named as belonging to another
repo's worktree.

## Deletion

Per #584's explicit instruction, this pass does **not** delete the 37
source files in `.git/`. Deletion is a separate, later change once this
classification has been reviewed.
