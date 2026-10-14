# Template drift doctor

blueprintx#109. `templates/python-common/bin/check_template_drift.py` reports which files a
scaffolded project should have received from BlueprintX but does not have. It is a reporter: it
always exits 0, and a run that could not compare says `SKIPPED` rather than passing.

## Provenance stamp

`scaffold_stamp_provenance` (`bin/lib/scaffold_provenance.sh`) writes
`.blueprintx-provenance.yaml` into every scaffolded project, service tiers and `lib-minimal`
alike. It records the tier, the review-bot roster choice, the BlueprintX version and the commit.
It is its own file because sourcing the service copy-list lib into `lib-minimal` made
`check_agents_md_bridge.sh` credit `lib-minimal` with copies it never makes.

- The file is written by BlueprintX at scaffold time and read by `check_template_drift.py`; do not
  edit it by hand.
- `tier` and `review_bot_roster` are read and decide what is compared. `blueprintx_version` and
  `blueprintx_commit` are provenance for a human and are not read.
- The comparison is always against the checkout's current template, not the stamped commit.
  Comparing against the stamped commit would need that commit's history in the checkout, which a
  generated project cannot assume, and would answer "what did this project start with" rather than
  "what has the template gained since". The stamp therefore does not tell "scaffolded before the fix
  landed" from "removed the file on purpose"; the report says so and leaves that to a human.
- The version comes from `git describe` and the commit from `git rev-parse` only when
  `BLUEPRINTX_ROOT` has its own `.git`. `git -C` walks up the directory tree, so a packaged install
  living under an unrelated repository (Homebrew's, for example) would otherwise stamp that
  repository's tag. Without a checkout the `BLUEPRINTX_VERSION` literal in `bin/blueprintx.sh` is
  used, then `unknown`; the commit is `unknown`, since the literal carries none.
- The filename is a literal in both the scaffold lib and the doctor's `_PROVENANCE_FILENAME`,
  kept in sync by hand: the writer ships with BlueprintX and the reader ships inside every
  scaffolded project, so no shared constant is reachable from either side.

## Reading the scaffold lib

The doctor derives "required files" from the lib's own output instead of keeping a second manifest
or parsing its shell source.

- `bash bin/lib/scaffold_python_templates.sh --list-copies --tier <tier> [--roster true|false]`
  runs `scaffold_copy_common_templates` with `cp` and `rm` replaced by printers and everything else
  that writes made inert. Each line is tab-separated: `COPY file|dir <source> <destination>` with
  the source relative to the checkout and the destination relative to the project, or
  `RM <destination>` for a path the scaffold deletes after copying.
- Because the shell itself expands globs, loops and variables, a copy written in any form is seen.
  The earlier regex reader missed any form it was not written for; the first version was blind to 29
  of 52 copies behind a line continuation.
- The doctor keeps only sources under `templates/python-common/` and `templates/common/`. A directory
  source delivers every tracked file under it, and a file that exists but is untracked (a draft a
  glob matched) is dropped.
- A missing lib, a missing `bash`, a failing dry run and an empty one are all `SKIPPED`, never a
  clean pass.
- A new copy that depends on a new opt-in flag is only treated as conditional if the dry run is
  taught that flag; today the only one is the review-bot roster.

## Conditional copies

The dry run is made twice in effect: with `--roster false` for a project that declined the roster
or whose stamp is silent, and with `--roster true` for one that opted in. `None`, a project
scaffolded before the stamp recorded the choice, stays on the declined side: reporting a file as
missing on a project that legitimately declined it is the false positive this design exists to
avoid.

## Should-fail witness

`tests/unit/test_template_drift_gate.py` is copied into every project so the doctor is itself
exercised by the generated project's own suite, against a stand-in lib that speaks the `--list-copies`
contract. `tests/test_scaffold_python_templates.sh` (BlueprintX's own tree) runs the same doctor
against the real lib and mutates it: dropping a copy stops it being required, and adding one in a
loop form is flagged.

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
