# Scaffolder prompt hierarchy + Cancel colour (#251, #253)

One branch, one PR (`feat/scaffolder-prompt-hierarchy-251`) — same surface (colour
semantics in `bin/lib/common.sh` and `bin/blueprintx.sh` / `bin/scaffold/*.sh`).

## Design decisions

- `PROMPT_PRIMARY` (bold blue), `PROMPT_SUB` (bold magenta / "pink"), `CANCEL`
  (aliased to `PROMPT_SUB` — both are "secondary but deliberate, never an
  error") are new escape codes in `bin/lib/common.sh`, **not** aliases of the
  existing RED/GREEN/YELLOW/BLUE/CYAN/MAGENTA (each already bound to one
  `print_status` level) — reusing one would repeat the exact #253 defect with
  a second colour.
- Placed in `bin/lib/common.sh` (BlueprintX-repo-only), **not**
  `templates/common/bin/lib/common.sh` / `templates/python-common/bin/lib/common.sh`
  (shipped to every generated project). "Which scaffolder question is a
  sub-question" is a concept of BlueprintX's own interactive menu, not
  something a generated project's own scripts need — shipping it there would
  leak a scaffolder-only concept into every user's repo.
- Hierarchy is carried primarily by the `[?]` / indented `└` glyph
  (`prompt_main` / `prompt_sub` helpers), colour only reinforces — so it
  survives `NO_COLOR` / a non-TTY pipe with the colour stripped.
- #256 (two-tone logo palette) is explicitly OUT of scope — not touched.

## Scope

- [x] #253 — Cancel uses `CANCEL` instead of `RED` (`bin/blueprintx.sh:117`, `:398`)
- [x] `PROMPT_PRIMARY` / `PROMPT_SUB` / `CANCEL` + `prompt_main`/`prompt_sub` helpers
      added to `bin/lib/common.sh`, shellcheck-clean
- [ ] Convert `read -r -p` sites to `prompt_main`/`prompt_sub` (~74 sites):
  - [ ] `bin/blueprintx.sh` (3 sites)
  - [ ] `bin/scaffold/python_ddd_service.sh`
  - [ ] `bin/scaffold/python_ddd_service_orm.sh`
  - [ ] `bin/scaffold/python_mvc_service.sh`
  - [ ] `bin/scaffold/python_mvc_service_orm.sh`
  - [ ] `bin/scaffold/python_lib_minimal.sh`
  - [ ] `bin/scaffold/ts_lib.sh` — ⚠️ collision with in-flight PRs #288/#292;
        edits kept to the 3 prompt lines only, no reordering
  - [ ] `bin/scaffold/ts_react_app.sh`
- [ ] `bash bin/ci/check_shell.sh` clean
- [ ] `make dry-run` / `make preview` still work
- [ ] Rendered before/after output pasted into PR body
- [ ] `NO_COLOR=1` / non-TTY pipe verified readable
- [ ] PR opened, `Closes #253` + `Closes #251`, verified via
      `closingIssuesReferences`

## Notes

- Collision warning (task brief): PRs #288 and #292 both touch
  `bin/scaffold/ts_lib.sh` — edits there are in-place on the 3 prompt lines
  only.
