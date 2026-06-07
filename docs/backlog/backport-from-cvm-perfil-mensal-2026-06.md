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

- [ ] **Ship a versioned `.gitlint`; the 72/80 limits are otherwise invisible.**
  gitlint's title ≤ 72 (T1) and body-line ≤ 80 (B1) caps are *defaults with no
  config file*, so contributors only discover them when a commit is rejected
  **after** the slow hook chain (tests + coverage) already ran. Ship a `.gitlint`
  alongside the `.pre-commit-config.yaml` that invokes it, stating the limits
  explicitly (`[title-max-length] line-length=72` +
  `[body-max-line-length] line-length=80`). Companion to the body-line item above;
  see the `.vscode` item below for the editor side.

- [ ] **`.vscode/settings.json`: associate `.gitlint` with the INI language.**
  Add `"files.associations": {".gitlint": "ini"}`. Without it the editor treats
  the extension-less dotfile as Python, so Pylance false-flags every INI section
  key (`"title" is not defined`, `"length" is not defined`, …) — noise the
  scaffold should never ship. This is the same `.vscode/settings.json` the MVC
  tier already touches for the interpreter path (see that item below); fold both
  keys into one shipped settings file. General rule: any non-`.py` dotfile the
  scaffold ships must declare its language so Pylance does not analyse it.

- [ ] **Replace `no-commit-to-branch` with a friendly `protect_main` hook.**
  The stock `no-commit-to-branch` aborts with a terse message and no next step.
  Ship a local hook (`bin/protect_main.sh`, `always_run: true`,
  `pass_filenames: false`) placed FIRST in `.pre-commit-config.yaml` so it fails
  fast before the slow test/coverage hooks. It blocks `main`/`master` and points
  at the project's own workflow (`make new_branch NAME=feat/…`). Document the
  guard + the allowed branch prefixes in `CONTRIBUTING.md` (kept in sync with
  `new_branch.sh`). Flow guard rail, not a control — bypassable with
  `--no-verify`, and there is no server-side equivalent on remote-less projects.

- [ ] **`.pre-commit-config.yaml`: only tool-owned `args` can move to a config
  file.** When tidying the config, remember the asymmetry: hooks wrapping a tool
  with its own config file (`ruff`→`ruff.toml`, `codespell`→`.codespellrc`,
  `gitlint`→`.gitlint`, `pydocstyle`→pyproject) can drop redundant `args:` and let
  the file own the settings. The `pre-commit/pre-commit-hooks` hooks
  (`check-yaml`, `trailing-whitespace`, `no-commit-to-branch`,
  `detect-aws-credentials`, …) read **CLI flags only** — they have no config file,
  so their `args:` must stay inline. Don't try to extract those.

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

- [ ] **Webhook seam: detect the platform from the URL; drop `WEBHOOK_PLATFORM`.**
  The opt-in webhook provider took both `WEBHOOK_PLATFORM` and `WEBHOOK_URL`, but
  the platform is redundant — it is inferable from the URL. Ship
  `detect_platform(url)` in the factory (substring match: `teams.microsoft` /
  `office.com` → teams, `slack` → slack; raise on unknown) and have
  `build_webhook(url)` take only the URL. Three coupled fixes proven in
  `cvm_perfil_mensal`:
  1. **`NullNotifier` for the opt-out path.** An empty `WEBHOOK_URL` previously
     crashed at import (the Teams adapter rejects an empty URL in its ctor).
     Return a no-op `NullNotifier` for a blank URL so `startup.py` imports without
     a live URL and "leave empty to opt out" is actually true.
  2. **Gate on the normalized production env; drop `WEBHOOK_ENV_GATE`.** That gate
     was a second env var duplicating `ENV`. Replace it with an allow-list: fire
     only when `normalize_text(ENV)` is in `{prod, production, …}` (lower-cased,
     accent-stripped). An allow-list stays silent for `dev`/`DEV`/`homolog`,
     unlike the fragile `!= "development"` deny-list (a mistyped `ENV` would have
     fired on a dev box). The config layer owns the bool; the orchestrator just
     executes it.
  3. **`.env.example`: drop both removed vars,** keep only `WEBHOOK_URL` with a
     comment on auto-detection + the production-only gate.

- [ ] **`check-urls` hook: never put fetchable example URLs in docstrings.**
  `bin/test_urls_docstrings.sh` fetches every `https://…` URL it finds in a
  docstring and fails on any 3xx/4xx (it does NOT follow redirects). Doctest-style
  `Examples` with fake paths (`https://hooks.slack.com/services/T000/…` → 404) or
  truncated real URLs (`…/l/channel/19%3A…` → 302) block the commit. The hook
  SKIPS host-only URLs (regex `https?://[^/]+$`), so write examples as bare hosts
  (`https://hooks.slack.com`), and refresh any stale docs URL to its current 200
  home. Note this in the python-common docstring conventions.

- [ ] **`.codespellrc`: make extending `ignore-words-list` part of the locale
  story.** When a project writes docs/comments in a non-English locale (e.g.
  Portuguese), the English `codespell` flags ordinary words (`nomes`, `caracteres`,
  `prefere`, `atual`, …) and blocks the commit. The scaffold cannot pre-populate
  the locale's vocabulary, but it should (a) document that `ignore-words-list` is
  the extension point and (b) keep the existing curated list rather than skipping
  whole files (which would hide real typos in code identifiers within those docs).

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
