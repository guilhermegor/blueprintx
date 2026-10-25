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

Every skeleton's scaffold answers `--list-copies`, not only the Python tiers: `python_api_service`,
`python_ddd_service`, `python_ddd_service_orm`, `python_mvc_service`, `python_mvc_service_orm`,
`python_lib_minimal`, `ts_react_app`, `ts_lib`, `bash_cli`, `etcher_chromeos` and `ventoy_usb`
(`bin/scaffold/<name>.sh --list-copies [--roster true|false]`). Each runs a `list_copies_step`
through the shared `scaffold_cli_list_copies` in `bin/lib/scaffold_provenance.sh`, which clears
`GITGUARDIAN_API_KEY` so the output never depends on the caller's environment. Files that are
rendered rather than copied (`README.md`, `pyproject.toml`, `package.json`) do not appear, and
prompt-driven optional copies are not listed. `tests/test_scaffold_list_copies.sh` checks all
eleven.

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
