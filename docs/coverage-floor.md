# **Coverage Floor — Design Record**

Explains `bin/check_coverage_floor.py`, shipped in `templates/python-common/`. Tracked as
[issue #149](https://github.com/guilhermegor/blueprintx/issues/149).

> **See also:** [Contributing](contributing.md) · [Troubleshooting](troubleshooting.md).

---

## The problem

`.coveragerc`'s `[report] fail_under = 80` is the coverage floor every scaffolded Python
project ships with, read by `pytest-cov` in both the pre-commit `coverage-check` hook and
the CI coverage gate. That number is only honest if the `[run] omit` list beside it is
accurate — and `omit` is exactly the shape of hand-declared list this repo distrusts
everywhere else (the same failure class `check_layer_imports.py`'s `.layer-policy.yaml` and
`check_docs_sections.py`'s required-page list both guard against): a plain list of glob
patterns nobody's test can contradict.

Widen one glob — turn `src/capabilities/*/infrastructure/*` into `src/capabilities/*` — and a
whole new capability's `domain/`/`application/` logic silently drops out of the coverage
denominator. `fail_under` still reads `80`, the suite is still green, and the layer
`CLAUDE.md`'s promise that `domain/`/`application/` are "pure Python, no I/O" is no longer
measured at all. Green, silent, wrong — nothing short of reading every capability's `omit`
entry by hand would have caught it.

## The floor is code-derived, not a second hand list

`bin/check_coverage_floor.py` walks `src/capabilities/*/{domain,application}/` via `ast`
(never source text) and collects every module that defines at least one function or method —
that structural fact is what "real logic" means here. An enum-only file
(`domain/enums.py`, already excluded by name in `.coveragerc`) defines classes but no
functions, so it is excluded correctly without a second hand rule about it.

Any such module that an `omit` pattern still matches is a finding — unless its **whole**
capability is named outright by a non-wildcard pattern (today `src/capabilities/example_feature/*`,
the shipped example). That exception set is read back out of the *same* `omit` list at
run time, never hardcoded, so a future named exception is picked up the same way
`example_feature` is today.

## Deliberately coarse — and that is the decision, not a lapse

⚠️ **The coarse boundary is the EXEMPTION granularity, not the detection granularity** — two
different things, and conflating them understates what the gate does.

- **Exemptions are capability-root and literal.** `whole_capability_exclusions()` reads back
  only non-glob, whole-capability patterns (today `example_feature`), and
  `must_stay_covered()` skips exactly those capabilities. A capability carrying merely a
  *narrower* exclusion (`src/capabilities/*/infrastructure/*`) is **not** exempt — it stays
  in scope.
- **Detection is per module.** For every non-exempt capability, `swallowed_by_omit()` checks
  each logic-bearing `domain/`/`application/` module against every `omit` pattern. **A single
  mis-omitted file inside a capability that already has narrower, legitimate exclusions IS
  caught**, and the failure names that file.

Measured 2026-09-18 against this PR's head, with a capability holding both a legitimate
`infrastructure/*` exclusion and one mis-omitted domain module:

```text
❌ src/capabilities/orders/domain/service.py: defines a function but is matched by
   omit pattern 'src/capabilities/orders/domain/service.py' — dropped out of the
   coverage floor's denominator
```

What the floor genuinely does **not** do is derive coverage expectations file-by-file — it
never asserts that a given module *should* exist or be covered, only that a module which
exists and defines a function must not be omitted. That is the fragile, hand-maintained map
this gate exists to avoid needing: a coarser floor that stays code-derived beats a finer one
that degrades back into a second hand-written list.

## Exemptions that are not findings

- **No `src/capabilities/` at all** (the MVC layouts) — the gate has nothing to check and
  exits 0 with an explanatory message.
- **A fresh scaffold** — only the shipped, already-excluded `example_feature` capability
  exists, so the derived "must stay covered" set is legitimately empty. This is the expected
  result on `make new`, not a broken detector; the gate's own test suite proves discovery
  works via a synthetic second capability.

It refuses to report success, however, when `.coveragerc` is missing, its `omit` list is
empty, or `src/` has zero `.py` files — those are "discovery is broken," never "nothing to
check."

## Branch coverage and the floor's measurement (#427)

`.coveragerc` sets `branch = True`: statement coverage marks an `if` fully covered the moment
either arm runs once, so the untaken arm is invisible. The floor was measured, not assumed.
Each tier was scaffolded and measured with `bin/ci/scaffold_lint_test.sh`-style generated
projects (not the template root, which pins different tool versions), statement-only first and
then with `--cov-branch` on the same suite:

| Tier | Statement-only | `--cov-branch` | Note |
|---|---|---|---|
| `ddd-service-native-db` | 100% | 100% | measured set is empty: all capability code outside `example_feature` is in `omit` |
| `ddd-service-orm-db` | 100% | 100% | same, so these two tiers give no evidence either way |
| `mvc-service-native-db` | 80% | 81% | branch coverage can rise: missed lines can be straight-line code with no branch of their own; 86% once `ExampleEntity` is exercised (#667, same unbound `pd` as #617) |
| `mvc-service-orm-db` | 76% | 76% | already below the floor before `branch = True`; not introduced by it |
| `lib-minimal` | 100% | 100% | two-file skeleton, nothing to branch on |

**The floor stays at 80.** #427 forbids lowering it to accommodate `branch = True`, and the
floor is shared by every tier that copies this file, so setting it to the worst tier (76)
would silently loosen it for `mvc-service-native-db` (81%) and for the DDD tiers' first real
capability code. Turning branch coverage on dropped no tier below its statement-only figure.

The one finding is a **pre-existing gap**: `mvc-service-orm-db` measures 76% against an 80
floor, in `model/example_entity.py` and `controller/_pipeline.py` (untaken branches). Closing
it means new tests for those two files, tracked in
[#617](https://github.com/guilhermegor/blueprintx/issues/617). Note that
`poe unit_tests` does not pass `--cov`; the floor is compared only by the pre-commit
`coverage-check` hook and the CI coverage gate.

`lib-minimal` ships its own `.coveragerc` and sets `branch = True` there too, so the metric
means the same thing in every tier. It declares no `fail_under`, which this change leaves as is.

## Wired on both sides

Pre-commit hook `coverage-floor` and the CI step "Run Coverage Floor Gate" in
`.github/workflows/tests.yaml` both run `bin/check_coverage_floor.py` — one implementation,
both surfaces, the same rule every `check_*.py` gate in this repo follows.

## Out of scope: the publisher-index half of #149

Issue #149 bundles a second, unrelated lesson: auditing a backlog seeded from a proxy (an
external index or vendor SDK's own coverage) against the real publisher's data, so an item the
proxy never covered doesn't silently vanish. That lesson is about **issue trackers and a data
publisher's catalog** — it has no natural home beside a coverage gate over `src/`, does not
touch this template, and is not a BlueprintX code change. It stays a documented follow-up
rather than being force-fit into this gate.
