# Contribution Guidelines

Thank you for considering contributing to our project! Please take a moment to review these guidelines to ensure a smooth collaboration.

## Branching Strategy

### Branch Naming Convention

All branches must follow the pattern: `<purpose>/<branch-task>`

**Available purposes:**

| Purpose         | Format                      | When to Use |
|-----------------|-----------------------------|-------------|
| Feature         | `feature/<name>` or `feat/<name>` | New functionality |
| Bugfix          | `bugfix/<description>` or `fix/<description>` | Bug resolution |
| Hotfix          | `hotfix/<description>` | Critical production fixes |
| Release         | `release/<version>` | Version preparation |
| Documentation   | `docs/<description>` | Documentation updates |
| Refactor        | `refactor/<description>` | Code improvements |
| Chore           | `chore/<description>` | Project maintenance tasks |

**Examples:**
- `feat/user-authentication`
- `fix/login-validation-issue`
- `docs/update-api-reference`

## Commit Message Standards

All commits must follow the [Conventional Commits](https://www.conventionalcommits.org/) specification: `<type>/<scope>`


**Available types:**

| Type       | Purpose |
|------------|---------|
| `build`    | Build system or dependency changes |
| `ci`       | CI configuration changes |
| `docs`     | Documentation updates |
| `feat`     | New features |
| `fix`      | Bug fixes |
| `perf`     | Performance improvements |
| `refactor` | Code restructuring |
| `style`    | Formatting changes |
| `test`     | Test additions/modifications |
| `chore`    | Maintenance tasks |
| `revert`   | Reverting changes |
| `bump`     | Version updates |

**Examples:**
- `feat(auth): implement OAuth2 integration`
- `fix(calculations): correct rounding errors in tax computation`
- `docs(readme): add installation instructions`

## Development Setup


1. **Dependency Management**:
   - Use Poetry (version specified in `requirements.txt`)
   - Avoid adding redundant libraries - check `pyproject.toml` first
   - Run `poetry install` to set up the development environment

2. **Pre-commit Hooks**:
   - Install with `make precommit_update`
   - This enables automatic:
     - Code linting
     - Formatting
     - Security vulnerability scanning
     - Large file detection
     - Secret key detection

3. **Testing Framework**:
   - Maintain the standard file structure:
     - Implementation: `src/<feat_name>.py`
     - Tests: `tests/test_<feat_name>.py`
   - Run comprehensive validation with: `poe unit_tests -k <keyword>`
        - This command executes:
            - **Ruff**: Linting, formatting, and flagging deprecated Python features
            - **Codespell**: Spelling verification in comments and docstrings
            - **Automated tests**: All test cases matching the project's testing standards
   - Ensure 100% test coverage for critical components
   - Run tests locally before pushing changes

4. **Test-Driven Development**:
   - Write tests before implementation when possible
   - Include normal operations, edge cases, error conditions, type validation, and checks for examples in docstrings
   - Maintain test fixtures for complex scenarios
   - Recommended to use UNIT_TEST_TEMPLATE.md for AI generation of unit tests, in order to implement test-driven development best practices and follow project standards

## Cross-Language Quality Parity

BlueprintX scaffolds more than one language (Python and TypeScript/JS today), and a quality
decision made only on one side quietly widens the gap between them. Two rules keep that from
happening silently:

1. **Every quality decision applies to all scaffolded languages**, unless that language's own
   community standard says otherwise — and when it does, **the community standard outranks the
   house rule**.
2. **These decisions live in `README.md` / `CONTRIBUTING.md` / `docs/`, never as a code
   comment.** The one exception is a QA-suppression comment (`noqa`, `complexity-ok`,
   `type: ignore`, `codespell:ignore` — blueprintx#303 exempts these explicitly). A config file
   (`ruff.toml`, `eslint.config.js`) may carry the rule line plus a short pointer comment; the
   long justification belongs in the docs, not inline.

**Precedence order when a house rule and a language standard conflict:**

1. The language's own community standard (PEP-8 / PEP-257 for Python, ECMAScript/TC39 for
   JS/TS, the equivalent for any language added later).
2. This repo's cross-cutting rule.
3. Style preference.

A house rule that contradicts PEP-8 is a **defect in the rule**, not in Python.

### Parity is by prohibited construct, never by number

Copying a numeric literal between two languages' linters is not parity — it can silently produce
the wrong rule on one side. Two measured examples:

- **`complexity: 2` in ESLint is *more* severe than `max-complexity = 2` in ruff**, because
  ESLint's cyclomatic-complexity counter counts `&&`/`||` short-circuit branches and ruff's
  mccabe engine does not (blueprintx#425). The same digit delivers a different rule.
- **PEP-8 requires a space around `=` when the assignment carries a type annotation
  (`x: int = 7`) and forbids one when it doesn't (`x=7`)**. A single "uniform spacing around `=`"
  rule would be wrong on both sides of that same language.

The correct parity is by *what construct is forbidden*, not by the number that enforces it: both
languages should forbid nesting and allow a composite condition, but the rules that deliver that
differ, because **neither linter's complexity rule can see nesting at all**.

⚠️ Ruff `C901` and ESLint `complexity` both measure **McCabe cyclomatic complexity** — a count of
decision points, blind to how they are arranged. ESLint `max-depth` measures **nested block
depth**, a different property. Measured witness, two functions with three `if`s each:

| function | shape | ruff `C901` | ruff `PLR1702` |
|---|---|---|---|
| three sequential `if`s | depth 1 | `is too complex (4 > 2)` | not flagged |
| three nested `if`s | depth 3 | `is too complex (4 > 2)` | `Too many nested blocks (3 > 1)` |

**The same number, 4, for opposite shapes.** So a tight `max-complexity` does not enforce the
nesting rule — it forbids a superset, rejecting the flat early-return form this project prefers
for exactly the complexity it is trying to reduce.

Python's nesting-specific rule is `PLR1702` (`too-many-nested-blocks`), and it is ⚠️ **not
configured today**: ruff gates it behind `--preview`, which `templates/python-common/ruff.toml`
does not enable, so selecting `PL` does not activate it (`warning: Selection PLR1702 has no
effect because preview is not enabled`). Until blueprintx#434 lands, **the Python and TypeScript
nesting policies are approximate, not equivalent** — Python bounds nesting only as a side effect
of bounding complexity.

### Mandatory question for new quality issues

An issue that proposes a new quality decision (a lint rule, a gate, a coding convention) must
answer, in its body, **"what is the shape of this in the other scaffolded languages?"** — even
when the honest answer is "no equivalent tool exists yet, tracked as prose, not a gate."

This is **not** a gate. "Was this decision applied to both language families?" is not
machine-decidable — it is a review question, so it stays prose reviewed by a human, never a
`bin/check_*.sh` script.

### Cross-language gate-parity snapshot (measured 2026-09-06)

| Quality gate | Python | TypeScript/JS |
|---|---|---|
| Cyclomatic-complexity ceiling | ✅ ruff `C901`, tier-scoped (1 for `tests/`, 2 for `src/`, 8 for `bin/`) — `check_complexity.sh` | ❌ none (blueprintx#168) |
| Function-length ceiling | ✅ 60 lines — `check_function_length.py` | ❌ none |
| Deny-by-default import/vendor policy | ✅ `.layer-policy.yaml` + `check_layer_imports.py` on every Python tier | 🟡 partial — `templates/ts-lib/eslint.config.mjs` has a per-layer vendor allowlist (blueprintx#345); `templates/react-spa-webpack/eslint.config.js` only has `eslint-plugin-boundaries`, which polices layer *direction*, not a vendor allowlist |
| Builtin-name shadowing | ✅ ruff `A` (blueprintx#421, closes #418) | ❌ none — no `no-shadow`/`no-redeclare` configured |
| Early-return shape | 🔧 in flight — ruff `RET` (blueprintx#426) | ❌ none |
| Nesting-depth ceiling | ❌ none — `PLR1702` is preview-gated and preview is off (blueprintx#434); `C901` bounds nesting only as a side effect | ❌ none — no `max-depth` |
| Coverage floor | ✅ `fail_under = 80` (`.coveragerc`) | ❌ no Jest `coverageThreshold` configured |
| Casing convention (functions/variables/import aliases) — row re-measured 2026-09-13 | ✅ ruff `N`, minus `N802` in `tests/**` (blueprintx#422, closes #422) | ❌ none configured — `@typescript-eslint/naming-convention` exists but is unused. No like-for-like gap: a JS/TS test name is a **string literal** passed to `it()`/`describe()`, not a function identifier, so the one real N802 collision this issue measured (a test name using upper-case for semantic emphasis) has no TS equivalent to conflict with in the first place. TypeScript also has no analogue to the type-prefix convention that would otherwise fight a constant-casing rule — this repo's Python house convention is Python-only |
| Broad-except / catch-safety | ✅ ruff `BLE` (blueprintx#440) on top of the already-selected `E722`/`S110` | ✅ `@typescript-eslint/use-unknown-in-catch-callback-variable` + `only-throw-error` (blueprintx#440/#443) — by construction, not transcription: JS has no typed catch clause to mirror `BLE`, so the TS side closes the one gap `strict: true`'s `useUnknownInCatchVariables` leaves open (`.catch(cb)` callbacks) instead |

Re-measure before trusting this table on a later read — it is a snapshot, not a standing fact.
The heading date covers the table as a whole; a row re-measured later carries its own date in
its first cell, so one fresh row never implies the other rows were re-measured with it.
Update the date in this heading when the WHOLE table is re-measured, so the next reader knows whether the gap
narrowed or widened.

### Rules scoped to BlueprintX, not inherited by scaffolds

Parity is the default, and it is about **languages**, not about the BlueprintX/generated-project
boundary. A few rules govern how *this repository* is written and deliberately stop at the edge
of `templates/`. When that is the answer, it is written down here — "we chose not to" has to be
as visible as "we did", or the next reader re-opens a settled question as if it were an
oversight.

| Rule | Scope | Why it stops here |
|---|---|---|
| **Prose language is en-US** (blueprintx#194) | BlueprintX's own prose | A generated project may legitimately be bilingual. `templates/python-common/bin/check_comment_language.py` is locale-agnostic *by design* — that is a feature of the shipped gate, not an omission. |
| **The `docs/` boundary** — `bin/ci/check_docs_boundary.sh` (blueprintx#536, scoped by #576) | BlueprintX's own `docs/` | Two reasons, and either alone would be enough. **(1)** The same path means opposite things on the two sides: `docs/backlog/` at this root is the violation the rule names, while inside `templates/<tier>/` it is a shipped product surface with its own gate (`templates/python-common/bin/check_backlog_ledger.py`, wired into that tier's pre-commit + CI), present in five tiers today — `ddd-service-native-db`, `ddd-service-orm-db`, `mvc-service-native-db`, `mvc-service-orm-db`, `lib-minimal`. A guard that cannot tell them apart is worse than no guard: it condemns a feature the repo deliberately ships. **(2)** A generated project's `docs/` answers to its own authors, exactly as its prose language does. |

Two consequences worth stating, because both were live options that were rejected:

- **No carve-out.** "Walk `templates/*/docs/` with `backlog/` exempted" was option (a) and would
  make BlueprintX the authority over a downstream project's `docs/` layout, for the sake of a
  rule the downstream project never agreed to. The carve-out list would then have to track every
  directory a skeleton legitimately ships — a second, drifting copy of the skeletons' contents.
- **No opt-in knob.** A configurable boundary the generated project inherits was option (c), and
  `check_docs_boundary.sh` therefore takes **no `--root` flag**, unlike the rest of the gate
  family. Under this decision there is only ever one tree to walk. A knob nothing turns is an
  invitation to widen the scope without re-deciding it, and the widening would be invisible in
  review as a one-word config change.

`tests/test_check_docs_boundary.sh` asserts the scope
(`test_templates_tree_is_deliberately_not_walked`): a planted violation under
`templates/<tier>/docs/`, alongside a tier's real `docs/backlog/`, must leave the gate green.
Re-pointing the gate at `templates/` turns that case red rather than quietly failing the repo
for a feature it ships.

## Pull Request Process

1. **Create an Issue First**:
   - Check existing issues at [GitHub Issues](https://github.com/guilhermegor/blueprintx/issues)
   - Open a new issue if none exists for your work
   - If the issue proposes a new quality decision, answer the mandatory question above in the
     issue body before scoping the work

2. **Opening a PR**:
   - Fill out the PR template completely
   - Include:
     - Detailed description
     - Changes made
     - Testing performed
     - Documentation updates
     - Any technical debt created

3. **Code Review**:
   - Expect constructive feedback
   - Address all review comments
   - Update documentation as needed
   - Keep commits logically organized

4. **Merge Approval**:
   - Requires at least one approval
   - All tests must pass
   - Code coverage should not decrease
   - Documentation must be updated

### PR file-count ceiling — blueprintx#551

A PR is capped at **90 cumulative changed files**, enforced by `bin/ci/check_pr_file_count.py`
in both pre-commit and CI (`pr-file-count` job). Above it, split at a natural seam — by
capability/tier, or whitespace-only vs content-changed — into PRs of 90 files or fewer each.

The number is measured, not chosen: CodeRabbit hard-refuses to review a PR above **100**
changed files (`Review skipped: N files exceed the limit of 100`), and a PR in that state can
never merge. Over the 100 most recent PRs, exactly **1** exceeded even 90 files, and the
largest legitimate PR in that set was 59 files — so 90 leaves headroom on both sides without
being a rule nobody pays.

## Ruff Rule Adoption Log

`templates/python-common/ruff.toml` only carries a short pointer comment beside each
rule-set entry in `[lint].select` — the full measurement and, where a rule needed a
case-by-case call, the reasoning for each finding lives here.

### `RET` (flake8-return) — blueprintx#426

Adopted whole, including `RET501` (a `return None` that duplicates the function's
implicit `None`) — not narrowed to only `RET505` (the "unnecessary `else` after
`return`" early-return check).

- **`RET505` and the rest of the family:** 0 findings measured across
  `src/ bin/ tests/ optional/` — the codebase already writes early returns
  everywhere. Adopting it is a zero-cost regression gate: it does not rewrite any
  existing code, it only stops a future `if: return … else: return …` shape from
  landing.
- **`RET501`:** 5 findings in `templates/python-common` (the scope the original
  measurement covered), all the same shape — a `close()` method (or, in one case,
  an async `__aexit__`/a YAML-loader callback) annotated `-> None` whose body ends
  in an explicit `return None`. **`bin/ci/scaffold_lint_test.sh` then surfaced 6
  more** in `templates/ddd-service-native-db/src/chassis/db_schema/infrastructure/`
  (one per SQL backend's `close()`) — a skeleton-owned tree `ruff check` from
  `templates/python-common` never reaches, so the original measurement could not
  see them; only running `poe lint` inside a real scaffolded project could. In
  every one of the 11, `None` is the function's *only* possible return value (per
  the rule's own message, "if it is the only possible return value") — none of
  them is a `-> X | None` function where a mid-function `return None` is a
  deliberate distinct outcome the caller consumes. All 11 were therefore residue
  and the line was deleted (never suppressed with `# noqa`):
  - `templates/python-common/bin/check_docs_sections.py::_ignore_unknown`
  - `templates/python-common/optional/browser_steps/tests/test_step_handlers.py::FakeDownloadInfo.__aexit__`
  - `templates/python-common/optional/chassis/db_wschema/infrastructure/csv_handler.py::CsvHandler.close`
  - `templates/python-common/optional/chassis/db_wschema/infrastructure/joblib_handler.py::JoblibHandler.close`
  - `templates/python-common/optional/chassis/db_wschema/infrastructure/json_handler.py::JsonHandler.close`
  - `templates/ddd-service-native-db/src/chassis/db_schema/infrastructure/{mariadb,mssql,mysql,oracle,postgres,sqlite}_handler.py::*Handler.close`

  If a future `RET501` finding **is** a deliberate `None` branch of a `-> X | None`
  function (the `None` is the result the caller consumes, not leftover
  boilerplate), the right fix is a line-scoped `# noqa: RET501` **with a reason**,
  not deletion — an unreasoned `noqa` is the same debt as an unreasoned comment.

### `N` (pep8-naming) — blueprintx#422

Adopted with two per-file-ignores, not whole. Re-measured 2026-09-13 (ruff 0.11.13):
`ruff check --select N --statistics src/ bin/ tests/ optional/` → 9 findings across 3
rules (an earlier count in the issue read 6 — stale; re-measuring is what the issue asked
for, not trusting the number it opened with).

- **`N802` (function name should be lowercase) — 5 findings, all false positives, ignored
  in `tests/**` only.** Every one is a test name that uses upper-case for **semantic
  emphasis** on the exact behaviour under test:
  `test_modules_with_no_policy_file_FAIL_rather_than_pass_silently`,
  `test_a_glob_governs_packages_NESTED_below_the_sublayer`,
  `test_a_dotted_deny_also_catches_the_RELATIVE_form`,
  `test_account_blocked_until_takes_the_LATEST_deadline_not_the_latest_notice`,
  `test_no_threads_is_not_a_THREAD_problem`. `tests/CLAUDE.md` asks a test name to
  describe the *behaviour*, not the function under test — the upper-case word is that
  description, not a casing slip. Renaming to satisfy N802 would erase the one thing the
  name is for. `N802` stays active everywhere else; only `tests/**` is exempt.
- **`N806` (non-lowercase variable in function) — 3 findings, all true positives, fixed by
  moving the constant to module scope.** All three are the same shape: a local `_ALL_CAPS`
  name assigned inside a function body — exactly PEP-8's "constants are module-level and
  upper-case" rule seen from the other side, since a local variable that *looks* like a
  constant is really just a plain variable wearing constant casing.
  `bin/check_assertion_weakening.py::changed_paths` (`_INT_MIN_FIELDS`) and
  `::_compare_call` (`_MIN_EQ_ARGS`), plus `bin/check_gate_integrity.py::changed_paths`
  (`_INT_MIN_FIELDS`, a near-duplicate of the first — same shape, separate file, out of
  scope for this issue). Fixed by hoisting each to a module-level `_NAME = value` beside
  the file's existing module constants; no behaviour change.
- **`N813` (camelcase module imported as lowercase) — 1 finding, evaluated and kept via a
  per-file-ignore.** `src/utils/xml_reader.py` imports `defusedxml.ElementTree as
  defused_et`. The lowercase alias is deliberate, not accidental: the file's own module
  docstring already states why `defusedxml`, not stdlib `xml.etree.ElementTree`, is the
  trust-boundary-safe parser, and the alias's job is to read as "the defused one" at every
  call site. Renaming it to satisfy N813 (e.g. `DefusedElementTree`) would only make that
  signal harder to read for no defect fixed, so this one file is ignored for `N813` rather
  than renamed.

See the cross-language parity table above for the TypeScript side of this decision — no
like-for-like gap, since a JS/TS test name is a string literal, not a function identifier.
### `BLE` (flake8-blind-except) — blueprintx#440

Closes the gap `E722` (bare `except:`, already selected via `E`) leaves open:
`except Exception:` / `except BaseException:` names a type but says nothing —
the same class of finding, one layer narrower.

- Measured 2026-09-16 (ruff 0.11.13): `ruff check --select BLE --statistics
  templates/` → 2 findings, both the SAME line in `_pipeline.py`
  (mvc-service-native-db and mvc-service-orm-db ship byte-identical files) — a
  documented five-mode degradation (`PipelineOrchestrator._enrich`) where
  splitting the `except` by mode would re-create the original defect (one
  clause remembered, the rest silently fall through). Fixed with `# noqa:
  BLE001` pointing at the method's own docstring rather than duplicating the
  five-mode rationale in a second place.
- 9 other broad handlers in the tree already carried a `# noqa: BLE001`
  comment that this rule was not yet selected to enforce — a suppression
  naming a rule that never runs looks identical to one that does, from
  either side. Selecting `BLE` is what makes those 9 pre-existing
  suppressions real.
- **`RUF` was measured in the same pass and NOT adopted.** `ruff check
  --select RUF --statistics templates/` → 150 findings (138 `RUF100`
  unused-noqa alone, mostly noqa comments anticipating rule families not yet
  selected — e.g. `N-` ahead of blueprintx#486 — plus 5 `RUF022`, 4 `RUF046`,
  3 unicode-ambiguity findings). Unlike `BLE`, this is real cost, not zero,
  so it is a deliberate separate decision rather than bundled into this
  issue: left for a follow-up issue to adopt (or narrow) on its own measured
  merits.

### TypeScript catch-safety — blueprintx#440 (already shipped, blueprintx#443)

JavaScript has no typed catch clause — there is one `catch (err)` per `try`
and no `catch (e: TypeError)` to require, so `BLE`'s rule cannot be
transcribed; parity here is by **intent** ("never handle what you cannot
identify, never swallow it"), not by construct. `templates/react-spa-webpack/
eslint.config.js` and `templates/ts-lib/eslint.config.mjs` already carry the
two type-aware rules that close the one gap plain `strict: true`
(`useUnknownInCatchVariables`) leaves open — a promise `.catch(cb)`
callback's parameter stays `any` even under strict mode:

- `@typescript-eslint/use-unknown-in-catch-callback-variable` — forces the
  same `unknown`-and-narrow discipline onto `.catch(cb)` callbacks.
- `@typescript-eslint/only-throw-error` — only `Error` values may be thrown,
  so a catch's `instanceof Error` narrowing can actually succeed.

Measured 2026-09-16: 4 `catch (err)` sites across both tiers' `src/`
(`react-spa-webpack`'s `use-cases.ts` + `use-cases.zustand.ts`, 2 each), no
`.catch(cb)` callbacks and no non-`Error` `throw` — both rules cost zero
findings today, same as the Python side.

## Best Practices

- **Keep branches focused** - one feature/bugfix per branch
- **Make small, frequent commits** - easier to review
- **Write descriptive commit messages** - explain why, not just what
- **Update documentation** - when adding new features
- **Follow existing patterns** - maintain consistency
- **Communicate early** - if you're stuck or need clarification

We appreciate your contributions and look forward to collaborating with you!
