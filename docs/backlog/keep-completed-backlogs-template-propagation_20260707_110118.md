# Propagate "keep completed backlogs" into the template docs guidance

Branch: _(future — not yet opened)_
Origin: follow-up to `fix/scaffold-online-uncommitted-changelog-desc` / PR #45, which flipped the
root `CLAUDE.md` "Backlog discipline" rule to **keep** completed backlog files. The shipped
templates still tell scaffolded projects to **delete** them — flip those so the template and the
rule agree.

## Finding (verified 2026-07-07)

All 6 tiers' `templates/*/docs/CLAUDE.md` (line ~26-27) still say:

> "the ledger is *this branch's* state — **delete it once every item is done**."

Files:
- [ ] `templates/lib-minimal/docs/CLAUDE.md`
- [ ] `templates/mvc-service-native-db/docs/CLAUDE.md`
- [ ] `templates/mvc-service-orm-db/docs/CLAUDE.md`
- [ ] `templates/ddd-service-native-db/docs/CLAUDE.md`
- [ ] `templates/ddd-service-orm-db/docs/CLAUDE.md`
- [ ] _(check for any other tier added since; see audit below)_

## To do

- [ ] Flip the wording in every tier's `docs/CLAUDE.md`: replace "delete it once every item is
      done" with **keep it as a record** — tick the last box + add a "Completed — kept as a
      record" note; never delete on completion. Match the root `CLAUDE.md` phrasing.
- [ ] Audit for any other shipped "delete on completion" text (footers, `.keep` notes, scaffold
      heredocs). **Use RAW grep**, not rtk-proxied grep — the rtk proxy returned a false-empty for
      `grep -i delete templates/` here; `rtk proxy grep -rniE "delete .*(item|box|ledger)" templates/`
      found it. Also sweep `bin/scaffold/*.sh` heredocs.
- [ ] Verify: `rtk proxy grep -rniE "delete .*(item|box|ledger|backlog)" templates/ bin/scaffold/`
      returns nothing after the flip.
- [ ] Update the existing lesson `branch-work-ledger-in-docs-backlog` (global store + repo
      `docs/blueprintx-lessons.md` mirror) "Scaffold into" once the template flip lands.

## Notes

- This is the "Scaffold into" execution of the existing lesson `branch-work-ledger-in-docs-backlog`
  — **not** a new lesson. No template runtime code changes; docs guidance only.
- Completed — kept as a record when done (do NOT delete this file; that's the whole point).
