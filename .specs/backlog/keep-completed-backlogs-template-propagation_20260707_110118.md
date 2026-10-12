# Propagate "keep completed backlogs" into the template docs guidance

Branch: `docs/keep-backlogs-template-propagation`
Status: **Completed — kept as a record** (2026-07-07).
Origin: follow-up to `fix/scaffold-online-uncommitted-changelog-desc` / PR #45, which flipped the
root `CLAUDE.md` "Backlog discipline" rule to **keep** completed backlog files. The shipped
templates still tell scaffolded projects to **delete** them — flip those so the template and the
rule agree.

## Finding (verified 2026-07-07)

Turned out to be **5** tiers, not 6 — the `react-spa-webpack` tier ships **no** `docs/CLAUDE.md`,
so it never carried the convention (nothing to flip there). The 5 that did said:

> "the ledger is *this branch's* state — **delete it once every item is done**."

Files (flipped to keep-as-record):
- [x] `templates/lib-minimal/docs/CLAUDE.md`
- [x] `templates/mvc-service-native-db/docs/CLAUDE.md`
- [x] `templates/mvc-service-orm-db/docs/CLAUDE.md`
- [x] `templates/ddd-service-native-db/docs/CLAUDE.md`
- [x] `templates/ddd-service-orm-db/docs/CLAUDE.md`
- [x] `react-spa-webpack` — N/A (no `docs/CLAUDE.md` shipped)

## To do

- [x] Flip the wording in every tier's `docs/CLAUDE.md`: replaced "delete it once every item is
      done" with keep-as-record — "tick the last box and add a 'Completed — kept as a record' note;
      do **not** delete it". Matches the root `CLAUDE.md` phrasing.
- [x] Audit for any other shipped "delete on completion" text (footers, `.keep` notes, scaffold
      heredocs), via **raw** grep — none found beyond the 5 tier docs (rtk-proxied grep gave a
      false-empty; `rtk proxy grep` found them).
- [x] Verify: `rtk proxy grep -rniE "delete .*(item|box|ledger|backlog)" templates/ bin/scaffold/`
      returns nothing after the flip — confirmed (exit 1, no matches).
- [x] Update the existing lesson `branch-work-ledger-in-docs-backlog` (global store + repo
      `docs/blueprintx-lessons.md` mirror) "Scaffold into" — marked done.

## Notes

- This is the "Scaffold into" execution of the existing lesson `branch-work-ledger-in-docs-backlog`
  — **not** a new lesson. No template runtime code changes; docs guidance only.
- Completed — kept as a record when done (do NOT delete this file; that's the whole point).
