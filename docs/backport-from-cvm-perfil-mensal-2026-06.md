# Backport backlog — discovered in `cvm_perfil_mensal` (2026-06)

Fixes and improvements found while building a real MVC service (`cvm_perfil_mensal`,
scaffolded from `mvc-service-native-db` + `python-common` + `common`). Each item is
a **template bug or gap** — applying these to the scaffolding stops every future
project inheriting them. Organized by the tier that should own the change.

**Source of truth:** the working implementation in `~/dev/cvm_perfil_mensal`
(branch `feat/perfil-mensal`). Where useful, the commit is noted.

> Status legend: `[ ]` not yet backported · `[x]` done in blueprintx.

---

## templates/common — language-agnostic (bin/lib, shared shell)

- [ ] **`bin/lib/common.sh`: define `resolve_default_branch()` and `_read_env_var()`.**
  Both were *referenced and documented* in sibling scripts but **never defined**,
  so `new_branch.sh`, `git_merge_to_main.sh` and `db.sh` died under `set -e`.
  - `resolve_default_branch [explicit]`: explicit arg → `$DEFAULT_BRANCH` →
    `origin/HEAD` → local `main` → `master`.
  - `_read_env_var NAME`: read `NAME=value` from `.env` (honor `$ENV_FILE`),
    preserving `#`/`$` in passwords, stripping one surrounding quote pair, last
    assignment wins. Bypasses Make's `$`/`#` expansion that corrupts passwords.

- [ ] **`bin/db.sh` (rename from `db_setup_schema.sh`): remove bare-name lines.**
  Lines containing only a variable name (e.g. `str_db_backend` on its own) execute
  as commands → `command not found` → abort under `set -e`. They were no-op typos.
  Also: rename the script `db_setup_schema.sh` → `db.sh` with subcommands
  `up|backup|restore`, and the recipe `db_setup_schema` → `db_up` (the old name
  undersold what it does: bring services up + ensure schema + migrate). Add
  `db_backup`/`db_restore` recipes + VSCode tasks (restore takes `DUMP=<path>`).

- [ ] **`bin/ship.sh`: trap is unbound-var-unsafe under `set -u`.**
  Expand the stage path into the trap immediately rather than referencing a var
  that may be unset at trap time: `trap "rm -rf '$str_stage_root'" EXIT` with a
  line-scoped `# shellcheck disable=SC2064` + reason.

- [ ] **Commit-message convention: gitlint caps body lines at 80 (B1).**
  The structured commit body (`  - topic → file`) must keep every line ≤ 80 chars
  (title ≤ 72). Note this in the commit-convention docs / the commit-code skill so
  the `→ filename` bullets are written short. Title-case, imperative, no period.

---

## templates/python-common — Python tooling shipped to every Python tier

- [ ] **Rename `bin/check_consistency.py` → `bin/check_docstrings.py`** (and the
  recipe `check_consistency` → `check_docstrings`, pre-commit id
  `check-consistency` → `check-docstrings`, VSCode task detail). The old name said
  nothing about *what* it checks. It verifies NumPy docstrings against the
  signature (param types, return type, raises).
  Three substantive fixes to the checker itself:
  1. **Parse the combined NumPy param form `a, b : type`.** The old matcher
     required the name immediately before the colon, so every combined entry was a
     false "missing docstring for parameter" (this alone was ~20 bogus warnings in
     one project). Add a `_param_names(line)` helper that returns all
     comma-separated names before `:`.
  2. **Slice the 140-line `check_file`** into focused helpers (`_is_checkable`,
     `_check_return_type`, `_extract_documented_return`, `_documented_param_type`,
     `_check_parameters`, `_check_raises`).
  3. **`Raises` documents ONLY directly-raised exceptions** (a literal `raise` in
     the function's own body), never propagated/implicit ones. The checker detects
     raises via AST `raise` statements only — it cannot see propagation through
     calls/C-libraries — so keeping `Raises` direct-only makes both directions
     ("documented but not raised" / "raised but not documented") strict and
     deterministic. Do NOT weaken the checker to tolerate propagated exceptions.

- [ ] **`.pre-commit-config.yaml`: `integration-tests` hook must tolerate an empty
  suite.** A fresh project has no integration tests → `pytest tests/integration/`
  exits 5 ("no tests collected") → the hook fails → **every commit is blocked**.
  Fix: `entry: bash -c "poetry run pytest tests/integration/ || [ $? -eq 5 ]"`
  (real failures, exit 1, still block). Consider the same guard for `unit-tests`.

- [ ] **Coverage badge: use `genbadge[coverage]`, not `coverage-badge`.**
  `coverage-badge` (abandoned 2022) imports the legacy `pkg_resources`, which
  **setuptools ≥ 81 removed** → `ModuleNotFoundError`. `genbadge` has no such dep.
  Recipe becomes: `pytest --cov=src` → `coverage report -m` → `coverage xml -o
  coverage.xml` → `genbadge coverage -i coverage.xml -o coverage.svg`. Update
  Makefile, tasks.sh (keep them mirrored), the manual pre-commit `coverage-badge`
  hook, and pyproject. **Track `coverage.svg`** (README badge references it),
  **gitignore `coverage.xml`** (transient input).

- [ ] **pyproject dev-deps must DECLARE every tool the recipes invoke.**
  `make lint`/`make test_cov` call `ruff`, `codespell`, `pydocstyle`, `pytest-cov`,
  `coverage`, the badge tool via `poetry run …`, but several were **undeclared** —
  they only worked by accident via PATH/pyenv shims and broke in a clean venv. Pin
  `ruff` to the pre-commit hook's minor so `make lint` and pre-commit agree.

- [ ] **`ruff.toml`: exclude `bin/`** (ruff-format tabifies the check tooling and
  trips E101) and set `target-version` to the **floor of `requires-python`**
  (e.g. `py310` when `>=3.10`), not a hardcoded older version.

- [ ] **`.editorconfig`: `[*.py]` must set `indent_size = 4` AND `tab_width = 4`.**
  With ruff's `indent-style = tab`, if `[*.py]` omits these it inherits
  `[*] indent_size = 2`, so tabs render as 2 spaces in editors — a recurring
  "why are my Python tabs 2 spaces?" trap.

- [ ] **`check-added-large-files`: exclude the tracked lockfile.**
  `poetry.lock` is legitimately > 500 kB; keep the guard for stray dumps/binaries:
  `exclude: (?i)^(data/large/.*|poetry\.lock)$`.

- [ ] **poetry.lock policy for service/app tiers: track it.** Reproducible installs
  across dev (Linux) and prod (Windows). Regenerate with `poetry lock` after dep
  edits. (Library tiers may legitimately gitignore it.)

---

## templates/mvc-service-* (and the typing chassis it vendors)

- [ ] **Document the dual-import-root trap in `tests/CLAUDE.md`.**
  With `pytest.ini` `pythonpath = . src`, a module is importable as BOTH `src.X`
  and `X` — **distinct module/class objects**. A test that constructs a
  `TypeChecker`-guarded class and passes it *another src-class instance* must
  import BOTH via the **bare runtime root** (`from utils.x import …`,
  `from view.y import …`), matching how the app runs — else isinstance fails with
  the baffling `X must be of type Foo, got Foo`. The plain `from src.X import …`
  convention is fine for classes whose ctor args are stdlib/paths only.

- [ ] **`config/startup.py`: temp-dir fallback** when a Windows network daily-infos
  path (`A:\…`) can't be resolved on POSIX (dev/CI), so import-time singletons
  don't explode off-Windows.

- [ ] **`.vscode/settings.json`: pick the interpreter for the production OS.**
  There is no OS-portable way to set `python.defaultInterpreterPath` (no
  `[platform]` branching for that key; `python.venvPath` is machine-scoped and
  rejected in workspace settings). If the service runs on **Windows**, set
  `"${workspaceFolder}/.venv/Scripts/python.exe"` — on Linux/macOS that path is
  absent and the extension auto-discovers `.venv/bin/python`. NEVER hardcode
  `bin/python` (breaks Windows). Ship `python-envs.defaultEnvManager: poetry`.

- [ ] **Library-coupling seam rule in the MVC `CLAUDE.md`.** Peripheral 3rd-party
  deps (network, vendor SDKs, OS APIs, exotic formats) go behind a `utils/` seam;
  the core data libs (`pandas` + the configured DB driver) may be used directly in
  model/view/controller; the stdlib is unrestricted. (Wording proven in
  `cvm_perfil_mensal/CLAUDE.md`.)

---

## templates/ddd-service-* — source of the runtime type-checking chassis

- [ ] **Harden `chassis/typing` at the source** (both native + orm tiers, and the
  copy mvc vendors). Two empirically-proven bugs:
  1. **Static/class methods invoked via instance break** — `_wrap_attribute` must
     preserve `@staticmethod`/`@classmethod`/`property` descriptors.
  2. **PEP 604 unions (`X | Y`) unhandled** — `get_origin` returns
     `types.UnionType`, not `typing.Union`, so union args bypassed validation /
     raised. Fix: `_UNION_ORIGINS = (Union, types.UnionType)` and branch on both.
  The hardened version lives in `cvm_perfil_mensal/src/utils/typing/` — lift it
  back so native + mvc inherit the fix instead of re-discovering it.

---

## How to consume this

Work tier by tier (common → python-common → mvc → ddd). For each item, open the
referenced file in `~/dev/cvm_perfil_mensal`, port the change into the matching
template file, tick the box, and verify against that tier's example project.
Delete this doc once every box is `[x]`.
