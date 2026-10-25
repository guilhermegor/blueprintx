# Template updates

A scaffold is a one-shot copy. A fix that lands in `templates/` afterwards reaches only
projects generated after it. `poe template_drift` is the reporter that closes that gap
(blueprintx#872).

## What it compares

For a project stamped with `tier` and `blueprintx_commit` in `.blueprintx-provenance.yaml`,
three versions of every template-managed file exist:

| Name | Where it comes from |
|---|---|
| base | the template file at the stamped `blueprintx_commit` |
| theirs | the template file in the BlueprintX checkout now |
| ours | the project's file |

The set of template-managed files is never listed by hand. Each tier's scaffold entry
answers `--list-copies` by dry-running its own copy steps (`bin/lib/scaffold_python_templates.sh`
for the service tiers, `bin/scaffold/python_lib_minimal.sh` for lib-minimal) and printing one
`COPY` or `RM` line per copy. The dry run stubs `cp`, `rm`, `mkdir`, `touch`, `chmod`,
`envsubst` and `print_status` through `scaffold_dry_run` in `bin/lib/scaffold_provenance.sh`,
so the output cannot disagree with what the scaffold does.

## What it reports

- Missing: the template ships a path the project does not have.
- Template changed since scaffold: ours equals base and theirs differs.
- Both changed: ours and theirs both differ from base and from each other.

A file the project edited while the template stood still is not drift. Files a scaffold
renders through `envsubst` (`pyproject.toml`, `LICENSE`, `README.md`, `SECURITY.md`) are not
verbatim copies, so they are outside the comparison, as are files copied from `bin/ci/`.
Copies guarded by an answer given at scaffold time (the review-bot roster) are listed exactly
when the dry run is given the matching value, read back from the stamp. Other guarded copies
(a GitGuardian key, publish targets) are not policed yet, and the dry run ignores the
caller's `GITGUARDIAN_API_KEY` so the verdict never depends on the environment. A file absent
at the stamped commit that the project wrote itself is reported as both changed, unless its
content already equals the current template, in which case it is the same.

## Why it self-skips

Without a BlueprintX checkout, a stamp, or a usable `blueprintx_commit` (absent, `unknown`, or
not in the checkout's history), the content section prints `SKIPPED content drift` and says why.
It never prints a clean verdict for a comparison that did not run. The command always exits 0.

## Applying updates: `poe template_update`

`poe template_update` reads the same base, ours and theirs data and acts on it. It is a dry run
unless `--apply` is passed. The checkout comes from `--blueprintx-root` or
`BLUEPRINTX_TEMPLATE_ROOT`, as for the reporter, and the reporter's resolution of the managed
paths is reused rather than repeated (`managed_sources` in `bin/check_template_drift.py`).

| Project file | Action |
|---|---|
| missing | add it, with the template's file mode |
| equal to base | fast-forward to theirs |
| equal to theirs, or theirs equal to base | nothing to do |
| edited locally and the template moved too | `git merge-file` base, ours, theirs |

A clean merge is written as is. A conflict is written with `<<<<<<< ours`, `||||||| base` and
`>>>>>>> template` markers and listed in the output. A file git cannot merge (binary content)
is listed as unmergeable and left untouched. A local edit is never overwritten silently, and a
file whose base is unknown (added to the template after the stamped commit) merges against an
empty base, so a differing local copy surfaces as a conflict.

`--apply` first runs `git switch -c chore/template-update-<short-sha>`, where the short sha is
the checkout's HEAD. It never writes to the branch you were on, and it stops before changing
anything when the branch cannot be created (not a git work tree, or the branch exists). It then
writes the files and leaves them uncommitted for review. `blueprintx_commit` in the stamp moves
to the checkout's HEAD only when every file applied cleanly; after a conflict the stamp is
unchanged and the command exits 1, so resolving the markers and running it again continues from
the same base.

Without a usable stamp, checkout or `blueprintx_commit` the command prints `SKIPPED update`
(or the reporter's `SKIPPED`) and exits 0 without touching the project.
