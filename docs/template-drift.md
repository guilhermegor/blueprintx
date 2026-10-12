# Template drift doctor

blueprintx#109. `templates/python-common/bin/check_template_drift.py` reports which files a
scaffolded project should have received from BlueprintX but does not have. It is a reporter: it
always exits 0, and a run that could not compare says `SKIPPED` rather than passing.

## Provenance stamp

`scaffold_stamp_provenance` (`bin/lib/scaffold_python_templates.sh`) writes
`.blueprintx-provenance.yaml` into every scaffolded project. It records which tier and which
BlueprintX commit the project came from. Without it the doctor has no baseline: it cannot tell
"scaffolded before the fix landed" from "removed the file on purpose".

- The file is written by BlueprintX at scaffold time and read by `check_template_drift.py`; do not
  edit it by hand.
- The version comes from `git describe` only when `BLUEPRINTX_ROOT` is itself a checkout. `git -C`
  walks up the directory tree, so a packaged install living under an unrelated repository
  (Homebrew's, for example) would otherwise stamp that repository's tag. Without a checkout the
  `BLUEPRINTX_VERSION` literal in `bin/blueprintx.sh` is used, then `unknown`.
- The filename is a literal in both the scaffold lib and the doctor's `_PROVENANCE_FILENAME`,
  kept in sync by hand: the writer ships with BlueprintX and the reader ships inside every
  scaffolded project, so no shared constant is reachable from either side.

## Reading the scaffold lib

The doctor derives "required files" by parsing the `cp` commands in the scaffold lib instead of
keeping a second manifest.

- One regex matches every `cp [flags] SRC DST`. SRC is rooted at `$COMMON_TEMPLATE_ROOT` or
  `$SHARED_TEMPLATE_ROOT` (braced or not), DST at `$str_project_path`. A SRC ending in `/.` is the
  wholesale directory-contents form.
- Backslash-newline is shell line-splicing, so it is spliced out before matching. Before this, a
  wrapped `cp` was skipped: 23 destinations were found where 52 were actually copied, and the
  doctor was blind to 29 of the files it exists to police.
- The splice runs once the lib has been found. A missing lib is the one case that yields an empty
  set, reported as `SKIPPED`; reading it unguarded raised `FileNotFoundError`.

## Conditional copies

A conditional copy (the review-bot roster) is added back to the required set only when the
provenance stamp says the project opted in. `None`, a project scaffolded before the stamp recorded
the choice, stays excluded: reporting a file as missing on a project that legitimately declined it
is the false positive this design exists to avoid.

## Should-fail witness

`tests/unit/test_template_drift_gate.py` is copied into every project so the doctor is itself
exercised by the generated project's own suite. It is the check that fails if the doctor goes
blind.

## Manual task

`poe template_drift` is never part of `lint`. Like the contract-drift check it needs a resource the
project does not vendor, here a BlueprintX checkout, and it always exits 0. It declares no
arguments, so poe passes extras straight through:
`poe template_drift --blueprintx-root /path/to/blueprintx`.

## Promote script mirrors

`bin/promote_offline_to_online.sh` transcribes, rather than sources, the `.github` copy of each
scaffold. The five Python service scaffolds share one manifest; `ts_lib.sh` adds the skeleton's own
workflows (`release-npm` rendered with the project name) plus the shared CLAUDE.md, CODEOWNERS and
PR template; `bash_cli.sh` renders `release.yml` with the project name. The three files every
non-service TS or bash scaffold takes from `templates/common/.github` live in one overlay helper.
The offline strip mirrors `apply_offline_mode` in `ts_react_app.sh`, `ts_lib.sh` and `bash_cli.sh`;
`bash-cli` has no `package.json`, so that part of the strip is a no-op there. The TS and bash tiers
never shipped the secret-scan key, so it is copied only when keyed.
