# Quality Rules

`quality-rules.yaml` at the repo root is the **machine-readable source**: one entry per
quality rule, with how it is implemented in every scaffolded language. This page is the
**reason** behind each entry — the measured cost, the construct it prohibits, and why the
number (when there is one) is what it is. `CONTRIBUTING.md` and `README.md` only point here;
neither repeats this table, so there is exactly one place a rule's rationale can go stale
(blueprintx#432).

`templates/python-common/bin/check_quality_rules.py` is the gate that keeps the YAML honest.
It can decide three things mechanically, and refuses to pretend it can decide a fourth:

| Decidable — the gate checks it | Not decidable — stays a review question |
|---|---|
| Every scaffolded language (discovered from `templates/*/skeleton.meta`) has an entry for every rule — a missing language is an error, not an omission | Whether two differently-worded rules in two languages actually prohibit the *same construct* |
| A `status: not-implemented` or `overridden_by:` entry carries a non-empty `note` explaining why | Whether a rule that is missing from one language *should* exist there |
| A declared `file` + `pattern` actually appears in the real config file it claims to describe | — |

The third check is what stops this table from becoming exactly the kind of stale
documentation `check_codespell_sync.sh` exists to catch for `.codespellrc`: a number written
here and never checked against the tool that is supposed to enforce it.

## Complexity

**Prohibits:** branching deep enough that one reader can no longer hold every path in their
head, or that a green test run stops saying *which* path executed.

Python uses ruff's `C901` (mccabe) at three different ceilings by tree — `tests/` 1, `src/` 2,
`bin/` 8 — because the argument differs per tree, not because the number was copied down.
`tests/` is the load-bearing one: a test with a branch tests two paths, and the green never
says which ran, so ceiling 1 is the mechanical form of "each test asserts one behaviour".
`bin/` sits at 8 because the gates living there are parsing tools by nature (argv, ruff
output, YAML, AST) — measured at ceiling 2, 74% of `bin/` was violating, a number nobody pays
and therefore a gate nobody keeps. See `templates/python-common/bin/check_complexity.sh`'s own
header for the full per-tree table.

TypeScript uses ESLint's built-in `complexity` rule, at **3** for `src/**/*.{ts,tsx}` and **2**
for test files — numbers measured independently against `react-spa-webpack`'s own source, not
inherited from the Python ceiling by symmetry. **The two numbers are not comparable
digit-for-digit**: ESLint's `complexity` counts `&&`/`||` as branches and mccabe does not, so a
literal "make TS = 2 because Python's `src/` is 2" would be *stricter* than intended
(blueprintx#425) — the whole reason `quality-rules.yaml`'s `intent:` field states the
prohibited *construct*, never a shared digit.

## Function length

**Prohibits:** a function long enough that its full behaviour cannot be read in one screen.

Both languages cap at **60 lines of logic**, but "logic" is measured differently. Python's
`check_function_length.py` subtracts the docstring before comparing against the ceiling — this
house mandates NumPy docstrings with `Parameters`/`Returns`/`Raises`, so a raw span measures
how well a function is *documented*, not how long it is (measured: 13 functions exceeded a raw
ceiling where 3 exceeded it docstring-excluded, and the two flagged first under the raw measure
were the two best-documented functions in the tree).

TypeScript's `max-lines-per-function` uses `skipComments: true` as the nearest available
option — not equivalent, since it skips every comment (including inline ones), not only a
leading doc block. The gap is accepted rather than compensated with a lower ceiling, because
every measured function in the shipped example sits 33+ lines under 60 either way. A **separate**
100-line ceiling applies to `.tsx` files: a component's returned JSX can legitimately run long
without representing added logic, and policing markup at the same ceiling as logic is a rule
people turn off (blueprintx#439) — kept as two permanently separate blocks, never merged even
if the numbers happen to match some week.

## Magic numbers

**Prohibits:** a bare numeric or string literal standing in for a meaning that should have a
name — most visibly an HTTP status code written as `404` instead of a named constant.

Python's `PLR2004` (part of ruff's `PL` select) is ignored inside `tests/**/*.py`: a literal in
a test IS the case under test, and naming it moves the case away from the assertion that reads
it (21 of 29 original findings were in `tests/`, all of that shape).

TypeScript's `@typescript-eslint/no-magic-numbers` was wired in blueprintx#453, the newest entry
in this table and the one that best demonstrates why `quality-rules.yaml` exists: before #453,
TypeScript had **zero** of the six gates this table now tracks parity for (blueprintx#430).
`detectObjects: true` is load-bearing, not cosmetic — without it, the object-property response
shape used by Fastify/NestJS (`{ statusCode: 201 }`) is silent, which is the framework idiom
`bin/rules/web.md`'s status-code convention exists to catch.

## One assert per test

**Prohibits:** a test whose failure message does not say which of several unrelated behaviours
broke.

Neither language enforces this mechanically **today** — both entries carry `status:
not-implemented`, which is the point of the field: an unimplemented rule with no entry silently
ages into "forgotten", where an explicit `not-implemented` with a reason stays visible and
trackable (blueprintx#431). Python's complexity-1 ceiling on `tests/` catches a *branching*
test but not a straight-line test carrying several sequential `assert` statements — a genuinely
different shape. `eslint-plugin-jest` is already a devDependency (for `jest/no-export`,
blueprintx#442) but its `max-expects` rule is not yet wired into `eslint.config.js`.

## Default arg spacing

**Prohibits:** nothing — this entry exists to demonstrate the `overridden_by:` field, the
"community standard beats the house rule" case blueprintx#430 established as the top-level
precedent this whole registry mechanises.

PEP-8 requires a space around `=` in a default argument **only when the parameter carries a
type annotation** — `def f(x: int = 7)` with spaces, `def f(x=7)` without. `ruff-format`
already enforces exactly this, so writing a house rule on top would either duplicate the
formatter (redundant) or contradict it (unenforceable, since the formatter always wins — the
same principle `ruff.toml`'s own `E701` comment states). `overridden_by: PEP-8` records that
explicitly, so the next reader sees a *decision*, not an oversight.

TypeScript carries no equivalent entry to override: a default parameter is always
`x: number = 7` with spaces, annotated or not, so there is no asymmetry for a house rule to
correct. `prettier` already produces the only correct spacing.
