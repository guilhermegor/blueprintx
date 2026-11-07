# **Conflict-Free Registries**

A library grows one module at a time, and each new module used to touch the same shared spots:
the package `__init__.py` (import and `__all__`), a docs nav, a README table, and often a
hard-coded count. Parallel PRs conflicted there, and with a strict "require up to date" ruleset
the conflict resolution changed the PR's own patch, so the review-thread gate (correctly) dropped
the earlier review. Every merge then cost every other open PR a fresh review.

The approach below was measured in `guilhermegor/layouts-cvm#55` and adopted here unchanged
(blueprintx#959).

## What was measured

- Two branches that each add an entry at **different positions** of a sorted, one-entry-per-line
  list merge with no conflict. Two entries between the **same** two neighbours still conflict;
  that overlap is rare and accepted.
- A stored count is a silent bug, not just a conflict: both branches change `18` to `19`, git
  sees identical edits and keeps one, and the merged text says 19 over a list of 20 entries.
- `merge=union` is rejected. GitHub's server-side merge and update-branch very likely do not run
  custom merge drivers, and union would keep both versions of a line both sides changed, which is
  the count bug again.
- Runtime discovery of `__all__` is rejected: mypy and IDEs cannot see names created at runtime.

## What ships

`bin/check_registry_order.py` (pre-commit `check-registry-order`, `poe lint`, the CI workflow)
fails when:

- an `__all__` in any `__init__.py` under `src/`, nested packages included, is not sorted (names
  starting with `__` first, then case-insensitive A-Z);
- an `__all__` is not one literal list of strings (`+`, `+=`, `sorted(...)`, a star or a second
  binding), because the gate cannot read it;
- an `__all__` holds more than one entry on a line, or an entry on a bracket line;
- a README or `docs/` Markdown file, outside fenced code, states a number next to a countable noun
  (`18 modules`, `5 endpoints`, ...). Derive the number or reword to "every module in the table".

Zero `__all__` lists under `src/` is a failure, never a pass.

The `lib-minimal` package template starts with `__all__` already in that shape, one entry per
line.

## Registering a new module

1. Add the module under `src/<package>/`.
2. Add its import to `__init__.py` in sorted position.
3. Add its name to `__all__` in sorted position, on its own line.
4. Run `poe lint`. If a rebase conflicts, keep both sides' lines and re-sort; the gate says
   whether the order is right.

## Proof

`tests/test_check_registry_order.sh` builds two branches from one base, each adding a module,
merges them with no conflict, and runs the gate on the result. Negative controls cover an
unsorted list, a one-line list, an entry on a bracket line, an unreadable `__all__`, a stored count
and a missing `__all__`.

## TypeScript library

`src/index.ts` in `templates/ts-lib` is the same shape: a barrel with one export statement per line
that grows with each module. The generated project's ESLint config enforces
`perfectionist/sort-exports` on that file, so parallel PRs add lines at different positions instead
of both appending at the end. The Docusaurus sidebar is a fixed list of the
template's own pages (`index`, `usage`, `examples`, `faq`, ...) that does not grow per module, and
there is no count in its docs.
