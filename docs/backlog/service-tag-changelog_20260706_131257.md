# Backlog — Service tag-driven changelog

Branch: `feat/service-tag-changelog` · Base: `aef44fd`
Spec: `docs/superpowers/specs/2026-07-06-service-tag-changelog-design.md`
Plan: `docs/superpowers/plans/2026-07-06-service-tag-changelog.md`

Give the four service skeletons a generated, tag-driven `docs/changelog.md` like `lib-minimal`
(offline `cz bump`; online `release.yaml`). Delete this file once every box is `[x]`.

## Tasks

- [x] **1** — `[tool.commitizen]` on the 4 service pyprojects
- [x] **2** — `bump_version` → `cz bump`; move `changelog` recipe to shared Makefile/tasks.sh (out of `library.mk`)
- [x] **3** — changelog page → `--8<-- CHANGELOG.md` include; seed `CHANGELOG.md`; add `pymdownx.snippets` to 4 mkdocs; delete lib duplicate page (**not deleted** — `python_lib_minimal.sh`'s `copy_mkdocs_templates` copies `templates/lib-minimal/docs/changelog.md` directly, never touching `python-common/docs/`; deleting would break the lib scaffold. Left in place; DONE_WITH_CONCERNS, see task-3-report.md)
- [ ] **4** — service `docs.yaml` runs `cz changelog`; fix #41 badge comments
- [ ] **5** — `release.yaml` (tag + GitHub Release, no PyPI) in python-common; lib scaffold strips it
- [ ] **6** — `contributing` Releasing section rewrite + protected-`main` highlight
- [ ] **7** — CLAUDE.md model docs + end-to-end scaffold verification (online/offline/lib)

## Notes / decisions

- `pyproject.version` online stays nominal (changelog reads tags; nothing reads it post-#41). `ponytail:`.
- `release.yaml` single source in `python-common/.github/workflows/`; lib strips it (has its own `release-pypi`).
- Two investigate-and-lock points: `cz bump` `--no-verify`/branch behavior (Task 2/7); `commitizen` group in docs job (Task 4).
- Capture generalizable lesson in `docs/blueprintx-lessons.md` + global store on completion.
- Do not push; user opens the PR.
