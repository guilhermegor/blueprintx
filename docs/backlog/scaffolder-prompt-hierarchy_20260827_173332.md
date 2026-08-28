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
- [x] Convert `read -r -p` sites to `prompt_main`/`prompt_sub` (74 sites, all converted):
  - [x] `bin/blueprintx.sh` (3 sites)
  - [x] `bin/scaffold/python_ddd_service.sh` (13 sites)
  - [x] `bin/scaffold/python_ddd_service_orm.sh` (13 sites)
  - [x] `bin/scaffold/python_mvc_service.sh` (13 sites)
  - [x] `bin/scaffold/python_mvc_service_orm.sh` (13 sites)
  - [x] `bin/scaffold/python_lib_minimal.sh` (9 sites)
  - [x] `bin/scaffold/ts_lib.sh` (3 sites) — ⚠️ collision with in-flight PRs
        #288/#292; edits kept to the 3 prompt lines only, no reordering
  - [x] `bin/scaffold/ts_react_app.sh` (8 sites)
- [x] `bash bin/ci/check_shell.sh` clean
- [x] `make dry-run` / `make preview` still work
- [x] Rendered before/after output pasted into PR body
- [x] `NO_COLOR=1` / non-TTY pipe verified readable (unchanged from every
      other `print_status` call — no NO_COLOR handling exists anywhere in
      this codebase yet; text stays legible with raw escapes around it)
- [x] PR opened (#298), `Closes #253` + `Closes #251`, verified via
      `closingIssuesReferences` — GraphQL returned both `251` and `253`

Completed — kept as a record.

## Notes

- Collision warning (task brief): PRs #288 and #292 both touch
  `bin/scaffold/ts_lib.sh` — edits there are in-place on the 3 prompt lines
  only.
