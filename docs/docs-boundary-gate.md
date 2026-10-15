# Docs boundary gate

`bin/ci/check_docs_boundary.sh` (blueprintx#536, extended to generated projects by #576) fails
when `docs/` holds working material instead of published documentation. BlueprintX runs it on
its own tree; every generated Python project gets a copy at `bin/check_docs_boundary.sh` and
runs it with `--root .` in pre-commit and CI.

## The rule

Everything under `docs/` must be published documentation. Anything else is redirected to the
place that owns it:

| Found in `docs/` | Belongs in |
|---|---|
| `backlog/` | `.specs/backlog/`; reader-facing content goes to `README.md` / `CONTRIBUTING.md` |
| a file whose name contains `lesson` | outside `docs/`; a lesson hardened into a rule goes to `CONTRIBUTING.md` as the rule |
| `design.md`, `plan.md` | `.specs/features/<feature-name>/` (#447) |
| `security.md`, `threat*.md` | the root `SECURITY.md` (GitHub only reads it from the root, `.github/` or the `docs/` root) |
| any `.superpowers*` path segment | that tool's own home |

The list is open: when a new kind of working material appears, add the case and its
destination.

## Design notes

- A denied directory is reported once and not descended into.
- Git-ignored entries are skipped, but only when `--root` is itself a repository top level,
  and with global git config disabled so local and CI verdicts agree.
- Symlinks are classified, then treated as leaves: following them re-enters the tree through
  longer paths.
- An unreadable `docs/` or subdirectory, or an empty `docs/`, fails: a check that cannot see
  its subject has not passed.
- From the BlueprintX root the gate never walks `templates/*/docs/`; those are skeleton
  content, verified by running the gate inside a generated project
  (`bin/ci/scaffold_lint_test.sh`).
