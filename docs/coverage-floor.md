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

The floor works at the **capability root**. It catches a new capability's logic being
wildcard-omitted wholesale. It does **not** catch a single mis-omitted file inside a
capability that already has narrower, legitimate exclusions. Closing that gap would mean
deriving coverage expectations file-by-file — precisely the fragile, hand-maintained map this
gate exists to avoid needing. A coarser floor that stays code-derived beats a finer one that
degrades back into a second hand-written list.

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
