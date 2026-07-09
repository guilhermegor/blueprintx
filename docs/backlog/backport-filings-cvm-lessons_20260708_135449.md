# Backport filings-cvm scaffolding lessons → BlueprintX templates

> **▶ STATUS (2026-07-08): all 8 lessons + the `.vscode` fix are IMPLEMENTED and VERIFIED
> (5/5 tiers green), not yet committed.** Two steps remain: (1) mirror the lessons into
> `docs/blueprintx-lessons.md`, (2) commit + open the PR. See the `⛳ CHECKPOINT` section below.
> Verification uncovered one real defect — the mypy `python_version` pin — now fixed; see Lesson 3.

**Branch:** `feat/backport-filings-cvm-lessons` (main is protected → PR required)
**Source:** `~/github/filings-cvm/docs/blueprintx-lessons.md` (grew to **8 lessons**, origins 2026-07-06 → 07-08)
**Started:** 2026-07-08

Applying the generalizable lessons captured in filings-cvm to the templates so future
scaffolds inherit them. The BlueprintX-own `docs/blueprintx-lessons.md` sections are
already-applied records (prior merged PRs), **not** pending. The ~98 global-store lesson files
are out of scope (most already backported). Scope grew from 4 → 8 lessons mid-effort (user
added the second wave); all 8 are covered below.

## Decisions (defaults, documented)
- `check_typing.py` + `enable_pages.sh` land in `templates/python-common/bin/` (beside
  `check_docstrings.py`); `enable_pages.sh` sources `bin/lib/common.sh` for `print_status`.
- ~~mypy floor pinned to **3.10**~~ **SUPERSEDED** — the pin itself was the defect. `mypy.ini` now
  carries **no** `python_version`; the floor is checked by the CI 3.10 matrix leg. See Lesson 3.
- Drop the **`3.9`** CI matrix leg (inconsistent with the py310 floor; lesson-3 companion:
  derive the matrix from `requires-python`).
- Coverage floor single-sourced in `.coveragerc [report] fail_under = 80`; pre-commit +
  CI drop the duplicated `--cov-fail-under=80` literal.

## Slices

### Lesson 1 — GitHub Pages `enable_pages` recipe (language-common; docs.yaml Actions deploy)
- [x] `templates/python-common/bin/enable_pages.sh` (port from filings-cvm, verbatim)
- [x] `enable_pages` target in `templates/python-common/Makefile` + `tasks.sh` (parity), wired as last `init` prereq
- [x] Correct the misleading `enablement: true` comment in `templates/common/docs_version/docs.yaml` + `templates/lib-minimal/.github/workflows/docs.yaml`
- [x] "Publicando a documentação (GitHub Pages)" section in `docs/contributing.md` (python-common + lib-minimal)

### Lesson 2 — `check_typing.py` AST pre-commit hook (python-common)
- [x] `templates/python-common/bin/check_typing.py` (generalized docstring; exclusions aligned
      with ruff/mypy: skip `typing`, `chassis`, `example_feature` parts)
- [x] `check-typing` local hook in `.pre-commit-config.yaml` (sibling to check-docstrings)
- **BLOCKER — RESOLVED (user chose fix+verify now).** The hook exposed 2 genuine doctrine gaps that
  would have reddened every DDD+MVC scaffold's CI. Both fixed in-branch and confirmed by the harness:
  - [x] `src/app/container.py` — `AppContainer` (frozen `@dataclass`) + `build()` (DDD native + orm);
        frozen-dataclass × metaclass verified at runtime by the DDD scaffold's pytest run
  - [x] `src/view/report_renderer.py` — `RenderToExcel` (MVC native + orm); covered by
        `tests/unit/test_report_renderer.py` (5 passed)
  - lib-minimal passed from the start.

### Lesson 3 — Gate parity + single-sourced coverage floor (language-common / python-common)
- [x] `.coveragerc`: add `[report] fail_under = 80`
- [x] `.pre-commit-config.yaml`: `coverage-check` reads `.coveragerc` (drop `--cov-fail-under=80` literal)
- [x] `tests.yaml`: mirror `ruff format --check`, `check-typing`, and coverage floor; drop `3.9` leg
- [x] `mypy.ini`: **`python_version` pin REMOVED entirely** (was `3.12`; the branch first changed
      it to `3.10`, which turned out to be the defect — see below)
- **VERIFICATION FINDING — the earlier "env leak, resolved" diagnosis was WRONG. Real defect,
  real fix, now verified.** Superseded text kept out; here is what actually happens:
  - `make lint` failed on `numpy/__init__.pyi:737: Type statement is only supported in Python
    3.12 and greater` in a **clean** env (`env -u VIRTUAL_ENV`), inside the scaffold's own venv.
    The env-leak theory was disproved: `mvc-service-native-db` and `lib-minimal` install the
    **identical** numpy 2.5.1 + mypy 2.2.0, yet only MVC failed.
  - ROOT CAUSE: the harness interpreter is **3.12**, so Poetry resolves `numpy 2.5.1`
    (`requires_python >= 3.12`), whose stubs use PEP 695 `type` statements. Pinning
    `python_version = 3.10` makes mypy parse those stubs — which belong to the *running*
    interpreter — under 3.10 syntax rules. lib-minimal escaped only because nothing in it
    imports pandas, so mypy never followed into numpy.
  - Pinning `python_version` **below the running interpreter is structurally unsound**: the stub
    set on disk always belongs to the interpreter that installed it. This would also redden the
    real CI 3.12/3.13/3.14 matrix legs, not just local runs.
  - REJECTED: capping numpy (fights Poetry marker resolution; freezes every 3.12+ project on a
    stale numpy) and `[mypy-numpy.*] follow_imports = skip` (both only move the break to the next
    dependency to adopt PEP 695 stubs — pandas 3.x already has).
  - FIX: drop the `python_version` pin; mypy uses the running interpreter, always consistent with
    the installed dependency set. The requires-python floor is enforced where it is sound — the
    **CI 3.10 matrix leg**, which runs mypy *on* 3.10 against a floor-compatible dep set — and
    version-too-new syntax in our own code is still caught by ruff `target-version = py310`.
  - Verified: all **5** tiers scaffold + `make lint` + unit tests green after the fix.
- [x] Gate-parity note in `templates/common/.github/CLAUDE.md` + one-line pointer in tier CLAUDE.md

### Lesson 4 — `act` tactics (language-common; skill guidance lives outside repo)
- [x] CLAUDE.md "Tooling" note on `act --matrix os:ubuntu-latest`, risky-single-leg, Docker Desktop socket
      (skill files `act`/`act-py` are outside this repo — note-only here)

## Second wave — 4 new lessons added to filings-cvm mirror (requested 2026-07-08)

### Lesson 5 — dotfiles-dev-lessons.md mirror (language-common)
- [x] `docs/dotfiles-dev-lessons.md` added to `.gitignore` Scaffoldable-lessons block
      (python-common + ts-common)
- [x] Both lesson mirrors added to `exclude_docs` in all 5 tier `mkdocs.yml` (belt-and-braces;
      blueprintx previously relied on gitignore alone — now excluded too)

### Lesson 6 — ship initial coverage.svg so README badge doesn't 404 (python-common)
- [x] `templates/python-common/coverage.svg` placeholder (genbadge-style "coverage: n/a")
- [x] `cp coverage.svg` wired into all 5 scaffold copy paths (after the README envsubst line)

### Lesson 7 — tabular_reader read-as-text, never infer-then-cast (python-common)
- [x] `src/utils/tabular_reader.py` `read_table` passes `"str"` (was `None`) to `_read_raw`;
      docstring states the read-as-text guarantee (blueprintx path is `src/utils/`, not filings'
      `optional/utils/`)
- [x] Unit test `test_read_table_reads_as_text_preserving_zero_padding_and_decimals`

### Lesson 8 — `_internal/ports/` macro-section behavioural interfaces (lib-minimal) — user chose "implement in lib-minimal now"
- [x] Source authored at `templates/python-common/optional/ports/` (`example_port.py` generic
      `ExamplePort(Generic[T], metaclass=ABCTypeCheckerMeta)` + `__init__.py`) — mirrors
      `optional/typing/` (the `_internal` nesting happens at scaffold time via the dest path, not
      in the source name; blueprintx-native adaptation of filings' `optional/_internal/ports/`)
- [x] `templates/lib-minimal/ports_CLAUDE.md` (port/adapter split guide; mirrors config_CLAUDE.md)
- [x] `bin/scaffold/python_lib_minimal.sh`: added `mkdir _internal/ports`, `copy_internal_ports()`,
      its call, and a new `ports.` → `<pkg>._internal.ports.` rewrite rule in `rewrite_internal_imports`
- [x] lib-minimal `CLAUDE.md` layout updated with `ports/`; pyproject `exclude=["src/**/CLAUDE.md"]`
      auto-covers `ports/CLAUDE.md` (no change needed)
- [x] STATIC-VERIFIED: py_compile OK; rewrite simulation yields correct `pkg._internal.ports.*` /
      `pkg._internal.utils.typing` paths; `bash -n` OK; check_typing skips it (Generic[T] base →
      metaclass inherited)

---

## ⛳ CHECKPOINT (2026-07-08, post-reboot) — VERIFICATION COMPLETE

**Branch:** `feat/backport-filings-cvm-lessons` — NOT committed (working tree only).
**All 8 lessons + `.vscode` `.coveragerc→ini` are IMPLEMENTED and VERIFIED.**

**Scaffold harness — all 5 tiers GREEN** (`env -u VIRTUAL_ENV bash bin/ci/scaffold_lint_test.sh <tier>`,
each: scaffold + `make lint` incl. check-typing + `make unit_tests`):

| Tier | Result | Covers |
|------|--------|--------|
| `lib-minimal` | ✅ 1 passed | L5, L6, L8 (`_internal/ports` applied) |
| `mvc-service-native-db` | ✅ 119 passed | L2 `RenderToExcel`, L7 `test_tabular_reader` (6), L5, L6 |
| `ddd-service-native-db` | ✅ | L1, L2 `AppContainer`, L3, L4 |
| `ddd-service-orm-db` | ✅ | shared `mypy.ini` regression check |
| `mvc-service-orm-db` | ✅ | shared `mypy.ini` regression check |

**Fixes made during this verification pass:**
- `mypy.ini`: removed the `python_version` pin (see the corrected Lesson-3 finding above). This was a
  genuine defect that would have reddened the CI 3.12/3.13/3.14 legs of every pandas-importing tier.
- `optional/ports/example_port.py`: added the missing `Raises` docstring section for
  `NotImplementedError` (check_docstrings warning on the new L8 file).

Note: `env -u VIRTUAL_ENV` is still the right way to run the harness (it keeps the parent venv out of
the child `make lint`), but it was **not** the cause of the numpy failure — that was the mypy pin.
A pre-existing `find_file_problems()` "documented but not raised FileNotFoundError" warning in
`tabular_reader.py` is untouched by this branch and left alone.

### Wrap-up
- [ ] Mirror the 8 lessons into BlueprintX `docs/blueprintx-lessons.md` ("Backported 2026-07-08"),
      plus the new mypy-pin lesson discovered here
- [x] Verify in a scaffolded project (not template root): all 5 tiers scaffold + lint + unit tests
- [ ] Commit, push, open PR (**awaiting explicit user OK**)
