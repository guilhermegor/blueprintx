# Backlog — standard mkdocs doc sections + remove masthead version badge

Branch: `feat/mkdocs-standard-doc-sections`. Two coordinated changes across every mkdocs site
in the family (5 scaffold tiers + root), batched because they touch the same `mkdocs.yml` files.

**Canonical section set (from wwdates):** Home · Usage · Examples · API Reference · FAQ ·
Contributing · Changelog. Decisions: root = tool-mapped full set; service tiers = full parity +
keep Architecture; masthead version pill removed from scaffold tiers **and** root (GitHub-release
version from Material's `repo_url` integration stays).

## A) Remove the masthead version badge (git-describe pill) — all sites

Files per site: `mkdocs.yml` wiring (`theme.custom_dir: overrides`, `hooks:`,
`extra_javascript: header-version.js`, `extra_css: version-badge.css`) + delete
`overrides/main.html`, `docs/javascripts/header-version.js`, `docs/stylesheets/version-badge.css`,
`mkdocs_hooks.py`. Shared source `templates/common/docs_version/`: drop `mkdocs_hooks.py`,
`main.html`, `header-version.js`, `version-badge.css` (keep `docs.yaml`). Update every scaffold's
copy steps + `mkdir`s.

- [ ] root blueprintx (revert what PR #40 added)
- [ ] lib-minimal (template + scaffold copy)
- [ ] mvc-service-native-db, mvc-service-orm-db, ddd-service-native-db, ddd-service-orm-db (+ their 4 scaffolds)
- [ ] remove the 4 shared assets from `templates/common/docs_version/`

## B) Add the standard nav sections + pages

- [ ] **lib-minimal** — add `Examples` + `FAQ` (pages `examples.md`, `faq.md`; nav; scaffold copy).
  Final nav: Home · Usage · Examples · API Reference · FAQ · Contributing · Changelog.
- [ ] **service tiers ×4** — add `Usage`, `Examples`, `FAQ`, `Contributing`, `Changelog` (keep
  `Architecture`). New pages per tier + commitizen block/changelog wiring where missing + scaffold
  copy. Final nav: Home · Usage · Examples · Architecture · API Reference · FAQ · Contributing · Changelog.
- [ ] **root blueprintx** — add `Examples` (top-level linking existing per-skeleton examples),
  `CLI Reference` (API-equivalent for the tool), `FAQ`, `Contributing`, `Changelog`. Real content
  (blueprintx's own docs), tool-appropriate.

## Verification
- [ ] `mkdocs build --strict` on each template tree (scaffold a lib + a service; build root).
- [ ] No masthead pill in built `site/`; Material GitHub version still renders (online).
- [ ] Nav shows the full section set per tier; no broken links; docs/CLAUDE.md file index updated (root).
- [ ] Update `docs/CLAUDE.md` (root) file index + nav-shape reference.
