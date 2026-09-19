# Quality gate blind spots — a measured audit

Resolves #169. **This is an audit only — no gate, config, or template file in this repo is
changed by this PR.** Every claim below is backed by a command that was actually run in a
throwaway scratch tree (never committed) and its real output, so this document does not claim
coverage it did not measure — that is the exact failure #169 exists to catch in the gates
themselves, and it would be self-defeating to reproduce it here.

Scratch tree: `/tmp/.../scratchpad/gate-audit/` (session-local, discarded — not part of this
repo). Ruff version used: `0.11.13`, matching the pin in `templates/python-common/ruff.toml`.

## Method

For each gate, a deliberately-bad fixture was written that the gate *should* catch, the gate
was run against it, and the result recorded as **CAUGHT** or **MISSED**. Where a fixture needed
a full tier layout (`.layer-policy.yaml`, `src/capabilities/.../domain/`), a minimal scratch
copy of that layout was built rather than a full `make dev` scaffold — sufficient because these
gates read only the files/policy they're pointed at, not the rest of the tree. Two of the runs
below (`check_function_length.py`, `check_docstrings.py`) hit gate-specific CLI quirks worth
recording alongside the finding: `check_function_length.py --root` is required or it silently
scans the *script's own* tree instead of the target (see its row); `check_docstrings.py` treats
parameter/`Raises` drift as a non-blocking warning by explicit design (its own docstring says
so), so "CAUGHT" there means "detected and printed," not "exit 1."

## Part 1 — the issue's own ruff-family audit, re-measured

#169 was filed 2026-08-16 with a table of ruff rule families the `[lint] select` list in
`ruff.toml` didn't yet cover. A month of work landed in between (ruff select grew from
`UP E F ANN B SIM I AIR ERA S PD D` to `UP E F ANN B SIM I AIR ERA S PD D TID W PL PT RET A N`
— `PL`, `RET`, `A`, `N` were adopted since). Re-running the issue's own method against the
*current* config, using one fixture covering all eight families at once
(`src/bad_families.py`, reproduced below in relevant part):

```python
def read_flag(flag: bool) -> None:        # FBT — boolean trap
    print("on" if flag else "off")        # T20 — print as log
def check_status(code: int) -> bool:
    return code == 42                     # PLR2004 — magic value
def make_path(a: str, b: str) -> str:
    return os.path.join(a, b)             # PTH118 — os.path instead of pathlib
def stamp() -> datetime.datetime:
    return datetime.datetime.now()        # DTZ005 — naive now()
def unused_arg_fn(used: int, unused: int) -> int:  # ARG001 — unused arg
    return used
def wide_signature(a, b, c, d, e, f, g, h, i) -> int:  # PLR0913 — 9 args > max-args=8
    ...
```

**Command 1 — current adopted config:**
```
ruff check --config templates/python-common/ruff.toml --no-cache src/bad_families.py
```
**Output:** `10 issues` — `D103 (7x)`, `PLR2004 (1x)`, `B904 (1x)`, `PLR0913 (1x)`.

**Command 2 — the families the issue listed as ungated, selected explicitly:**
```
ruff check --isolated --select FBT,PTH,T20,TRY,DTZ,ARG --no-cache src/bad_families.py
```
**Output:** `7 issues` — `T201 (2x)`, `DTZ005`, `TRY003`, `ARG001`, `FBT001`, `PTH118`.

| Family | Issue's 2026-08-16 verdict | Re-measured 2026-09-17 | Status |
|---|---|---|---|
| `PLR2004` (magic value) | real, ungated | **CAUGHT** — `PL` is now selected | ✅ resolved since filing |
| `PLR0913` (too many args) | real, ungated | **CAUGHT** — `PL` is now selected, `max-args=8` | ✅ resolved since filing |
| `FBT` (boolean trap) | real, high value | **MISSED** — not in `select` | still open |
| `T20`/`T201` (print as log) | real | **MISSED** — not in `select` | still open |
| `PTH` (pathlib) | real | **MISSED** — not in `select` | still open |
| `DTZ` (naive datetime) | real, contradicts provenance doctrine | **MISSED** — not in `select` | still open |
| `ARG` (unused arg) | real | **MISSED** — not in `select` | still open |
| `TRY004`/`TRY003` | TRY004 real; TRY003 explicitly rejected as noise | `TRY003` still fires when selected (confirms the issue's own rejection reasoning was correct — it *would* be noisy) | no change recommended |

**Finding:** the issue's central "what does the gate not catch" claim from 2026-08-16 is
**half stale**. `PLR0913`/`PLR2004` were fixed by unrelated work in the interim (`PL` family
adoption). `FBT`, `T20`, `PTH`, `DTZ`, `ARG` remain genuinely ungated today, confirmed by direct
measurement rather than re-assumed from the old table.

## Part 2 — the issue's "no linter rule at all" list, re-measured

| Claimed gap (issue body) | Re-measured | Evidence |
|---|---|---|
| Cyclomatic complexity (#167) | **RESOLVED since filing.** `templates/python-common/bin/check_complexity.sh` now exists (landed via #224). | See gate test below — CAUGHT. |
| Import boundaries (#138/#139) | **RESOLVED since filing.** `templates/python-common/bin/check_layer_imports.py` now exists with `.layer-policy.yaml`. | See gate test below — CAUGHT. |
| Dead code (unreferenced function) | **Still a real gap**, confirmed live. | `ruff check --isolated --select F` on a fixture with an unused, unexported top-level function → `All checks passed!`. Pyflakes' `F401`/`F841` cover unused imports/locals, never an unreferenced top-level def. Already tracked: **#332** "dead-code detection — measured, and the scaffold inverts where it pays off" (open). |
| Duplication / copy-paste | **Still a real gap.** No `jscpd`/`pylint`-duplicate-code in any tier's dev deps (checked `pyproject.toml` `[tool.poetry.group.dev.dependencies]`). Already tracked: **#305** "adopt gitleaks, osv-scanner, jscpd, semgrep" (open, jscpd is the duplication detector). | dependency audit |
| Branch coverage (line-only floor) | **Still a real gap as of this writing, but already being fixed.** `.coveragerc` `[run]` has no `branch = True`. **Open PR** "feat(python-common): branch coverage, floor measured then set" (closes #427) already measures the per-tier delta and lands the fix. | `.coveragerc` read + open-PR check |
| Mutation testing | **Still a real gap, untracked.** No `mutmut`/`cosmic-ray` in any tier's dev deps. | dependency audit |
| The "convention has no executor" mechanism (issue's Scope item 4) | **In flight, narrower than the issue asks.** Open PR "feat(quality): machine-readable quality-rule registry + validation gate" (closes #432) adds `quality-rules.yaml` + `check_quality_rules.py` — exactly the shape the issue describes (a registry cross-checked against real config). Registered rules today: `complexity`, `function-length`, `magic-numbers`, `one-assert-per-test` (`not-implemented`), `default-arg-spacing`. **None of the 5 ungated ruff families from Part 1, dead code, duplication, or mutation testing are registered in it yet**, and the mechanism is not on `main` at all — it lands with #432's own open PR, and landing it will not by itself point the registry at this audit's findings. | PR body read via `gh pr list --search` |

## Part 3 — gates actually run against a deliberately-bad fixture

| Gate | Fixture | Command | Result |
|---|---|---|---|
| `check_complexity.sh` | 3-level nested `if` (cyclomatic 7) in a scratch `src/` | `bash check_complexity.sh --root <scratch>` | **CAUGHT** — `C901 'classify' is too complex (7 > 2)`, exit 1 |
| `check_layer_imports.py` | `src/capabilities/foo/domain/entities.py` importing `requests` directly, against a copy of `ddd-service-native-db/.layer-policy.yaml` | `python3 check_layer_imports.py` (cwd = scratch root) | **CAUGHT** — `'requests' is not allowed in layer 'capabilities/*/domain'`, exit 1 |
| `check_function_length.py` | 72-line function body | `python3 check_function_length.py --root <scratch>` | **CAUGHT** — `long_function() is 72 lines (max 60)`, exit 1. ⚠️ Run *without* `--root` first, by mistake — it silently scanned the real `templates/python-common` tree (205 files, exit 0) instead of erroring. `PATH_ROOT` defaults to a path relative to the script's own location (`bin/`), not to cwd, so a caller that forgets `--root` gets a false "clean" on a tree it never intended to check. Not a defect in this PR's scope to fix, but worth a one-line note in the script's own `--root` help text. |
| `check_docstrings.py` | function missing the `b` parameter in its NumPy docstring | `python3 check_docstrings.py` (cwd = scratch, `src/` present) | **CAUGHT, non-blocking by design** — printed `Missing docstring for parameter b`, but exits 0 ("params and raises drift are soft warnings" per the file's own module docstring; only return-type mismatches are hard errors). Confirmed working as documented, not a gap. |
| `check_comment_language.py` | a `#` comment and a one-line PT docstring, both Portuguese | `python3 check_comment_language.py <file>` | **PARTIALLY CAUGHT** — flagged the `#` comment (`reads as Portuguese [esta]`) but not the docstring `"""Soma dois numeros."""` (no accents, no recognized PT function word in that short a string — consistent with the gate's documented function-word heuristic, not re-verified further here). Noted, not filed — would need reading `SET_PT_WORDS` to confirm whether this is a real gap or working as calibrated. |
| `.pre-commit`/`bin/ci/check_shell.sh`'s shellcheck invocation | `local result=$(echo hi)` (SC2155) + `echo $result` (SC2086, unquoted) | `shellcheck -x --severity=warning <file>` (the exact invocation `check_shell.sh` uses) | **PARTIALLY CAUGHT** — SC2155 caught (`warning` severity). SC2086 (unquoted variable expansion — a common real bug class) is `info` severity, below the `--severity=warning` floor, and is not one of the two codes (`SC2030`,`SC2031`) the script's second targeted pass adds. Confirmed at `--severity=info` that shellcheck itself reports SC2086 — it is filtered out by the gate's own severity floor, not absent from shellcheck's ruleset. |
| `eslint` `no-magic-numbers` (TS parity check, not a Python gate) | n/a — config read, not run | `grep no-magic-numbers templates/{react-spa-webpack,ts-lib}/eslint.config.*` | **CAUGHT (already wired)** — landed via PR #456, both TS skeletons. Cited only to confirm the cross-language parity item from #425/#169 is not itself stale. |

## Gates NOT tested, and why

Time-boxed to the gates most load-bearing for #169's own claims (ruff select, complexity,
layer imports — the issue's named examples) plus a representative sample from each remaining
family (`bin/check_*.py`, `bin/ci/*.sh`). Not tested, with reason:

- **`check_all_exports.py`, `check_assertion_weakening.py`, `check_backlog_ledger.py`,
  `check_comment_budget.py`, `check_contract_drift.py`, `check_coverage_floor.py`,
  `check_dtypes.py`, `check_fixture_scope.py`, `check_migration_slugs.py`,
  `check_provenance.py`, `check_rmw_race.py`, `check_sql_guards.py`, `check_typing.py`,
  `check_gate_integrity.py`** — each has its own should-fail negative-control test already
  living in `tests/unit/`/`tests/integration/` per this repo's own "should-fail witness"
  convention (documented per-gate in `templates/python-common/CLAUDE.md`); re-deriving a
  fixture for each here would duplicate coverage that already exists and is CI-enforced,
  rather than surface a new blind spot. Reading `.coveragerc` and the dev-dependency list
  (Part 2) covered the two gaps in this group that mattered for #169 (coverage floor shape,
  mutation testing absence) without re-running each script.
- **`check_docs_code_refs.py`, `check_docs_sections.py`** — documentation-structure gates, out
  of scope for a *code*-quality-gate audit; #169's own body is scoped to code conventions.
- **`check_clean_index.sh`, `check_unix_filenames.sh`** — simple, single-purpose gates (empty
  index at push time; filename character set) with low ambiguity about what they catch; skipped
  for time.
- **`bin/ci/check_actions.sh`, `check_codespell_sync.sh`, `check_docs_build.sh`,
  `check_gate_staleness.sh`, `check_git_remote_guard.sh`, `check_markdown.sh`,
  `check_project_name_identities.sh`, `check_review_bot_roster_optout.sh`,
  `check_sed_portability.sh`, `check_spelling.sh`, `check_version_sync.sh`,
  `validate_meta.sh`** — these are root-repo-only gates (BlueprintX's own tree, not the
  scaffolded templates), and #169 is scoped to the *scaffolded project's* quality gate
  (`ruff.toml`'s `select`, the `bin/check_*.py` family it ships). Auditing BlueprintX's own
  CI hygiene is a different, legitimate audit but not this one.
- **`eslint.config.{js,mjs}` full rule audit** — the issue is explicitly about the ruff
  `select` list; a full ESLint-vs-ruff parity re-measurement is `CONTRIBUTING.md`'s own
  documented, dated table (see "Cross-Language Quality Parity") and re-measuring the whole
  table is a separate task from this one gate.
- **A full `make dev`/`scaffold_lint_test.sh` scaffold** was not run. Every gate tested above
  reads only its own target path/policy file, not the rest of a generated project, so a minimal
  scratch layout was sufficient and faster; nothing here depended on a real Poetry venv or the
  full pre-commit chain.

## Proposed follow-ups

For the owner to file, not filed by this PR:

1. **Adopt `FBT`, `T20`, `PTH`, `DTZ`, `ARG` in `ruff.toml`'s `[lint] select`**, following the
   measure-then-adopt pattern the file's own comments already use for `RET`/`A`/`N` (per-family
   real-finding count across `src/`+`bin/`+`tests/`, per-file-ignores for legitimate exceptions
   like `T20` in `bin/`). `DTZ` needs its own resolution first — the issue's contradiction with
   the provenance doctrine's tz-aware `updated_at` (is a run timestamp deliberately naive, or a
   bug?) has to be decided before the rule can be turned on without immediately failing.
2. **Register the five families above (once adopted), dead code (#332), duplication (#305), and
   mutation testing in `quality-rules.yaml`** (#432's registry) once each lands — that registry is
   itself still in flight on #432's open PR, so it has to land before anything can be
   registered in it, and landing it does not by itself cover the gaps this audit measured.
3. **Add mutation testing** (`mutmut` is the natural fit — pure Python, no service dependency)
   to at least one tier as a measured pilot, mirroring how branch coverage was piloted before
   the floor was set (the open branch-coverage PR closing #427 is the template to follow).
4. **Widen `bin/ci/check_shell.sh`'s shellcheck severity, or explicitly allowlist `SC2086`**,
   with the reasoning written down either way — right now the gap is silent (nothing states
   that `--severity=warning` plus a two-code targeted pass deliberately excludes SC2086).
5. **A one-line note in `check_function_length.py`'s `--root` handling** (or its `--help`
   text) that omitting `--root` defaults to the script's *own* directory, not cwd — the
   silent-wrong-target trap measured in Part 3.
6. **Link this document from `mkdocs.yml` nav** — not done in this PR. Two open PRs already
   touch `mkdocs.yml` (`quality-rules.yaml`'s registry PR, and the complexity-ceiling docs PR);
   adding a third concurrent edit to that file risks an avoidable merge conflict. File as a
   trivial follow-up once those land.

## Documentation

This file is the documentation deliverable for #169. `mkdocs.yml` nav registration is listed
above as a proposed follow-up (see rationale), not done here.
