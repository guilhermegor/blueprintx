# CLAUDE.md — src/config/

Border rules for the configuration layer. This directory holds **declarative
configuration, startup singletons, and the connection factory — nothing else.**

## What belongs here

- **`startup.py`** — builds runtime singletons once at import (logger, env, output
  paths). Copied from `templates/python-common/src/config/`; edit it there, not in a
  scaffolded project.
- **`connection_db.py`** — the DB connection/engine factory (reads `DB_BACKEND` from
  `.env`, lazy-imports the one configured driver).
- **YAML config** — `inputs.yaml` / `outputs.yaml` (and any `*_dev.yaml`/`*_prd.yaml`
  variants): declarative values only, no logic.
- **`queries/`** — SQL query files, one per `<db>__<table>__<purpose>.sql`, each opening
  with a header comment (database/schema, table(s), purpose). Keep inline SQL out of code.
- **`contracts/`** — `FileContract` declarations, one per input source (see the dedicated
  section below).
- **`signatures/`** — e-mail signature templates.

## What does NOT belong here

- **No data access / business logic** — that is the model's job (`src/model/`).
- **No rendering** — that is the view's job (`src/view/`).
- **No orchestration** — that is the controller's job (`src/controller/`).
- **No secrets in tracked files** — real values live in the git-ignored `.env`; mirror
  every key (with a placeholder) in the tracked `.env.example`.

**Why:** config is the one layer every other layer imports, so it must stay free of
side-effectful logic. A singleton that does I/O at import, or business rules hidden in a
YAML loader, couples the whole app to this layer and makes it untestable. Keep it
declarative; push behaviour outward.

## Runtime type-checking in the config layer

Config-layer functions carry the runtime `@type_checker` like the rest of the codebase
(`connection_db`'s factories, `env_config.resolve_config_path`, `startup.output_path`) — the
"enforce inputs/outputs everywhere" rule has no by-layer exemption. The only nuance is the
**import path**, because the engine is injected at a layout-dependent location:

- **MVC-only files** (`connection_db.py`) import it directly: `from utils.typing import
  type_checker`.
- **Shared files** (`startup.py`, `env_config.py` — copied into *both* MVC `utils.typing` and
  DDD `chassis.typing`) import it through a portable shim so the same code works in either
  layout:

  ```python
  try:
      from utils.typing import type_checker
  except ModuleNotFoundError:  # DDD ships the engine as chassis.typing
      from chassis.typing import type_checker
  ```

The shared `utils/` helpers (decimals, dtypes, …) are decorated too, through the **same shim**
(they ship to both layouts, like the shared config files). Do **not** hard-import `utils.typing`
in any shared file (it breaks the DDD layout); use the `try/except` shim above. Only files that
exist in a single tier (e.g. `connection_db.py`, MVC-only) may hard-import `utils.typing`.

## The contracts/ sub-package

- **One contract per file** (`cadastro.py`, `orders.py`, …): a module docstring plus a single
  `FileContract` constant. New input → new file.
- `contracts/__init__.py` re-exports every contract **and** the machinery (`FileContract`,
  `find_file_problems` from `utils/tabular_reader`), so callers use one import:
  `from config.contracts import CADASTRO, ORDERS, find_file_problems`.
- Contracts are **declarations**, not validators — the validation engine lives in
  `utils/tabular_reader`. Contracts say *what shape*; the seam enforces it.
- A contract that constrains nothing is still explicit: `FileContract(name, key, (), ())`.
- **`config/contracts/` is the ONLY place a `FileContract` is constructed.** Model loaders
  and the controller boundary **import** the instances; they never build one inline.
  **Statically enforced** — ruff (`TID251`) bans constructing `FileContract` outside this
  package; the few files that import the *class* only for a type annotation (controller,
  notifier) carry a line-scoped `# noqa: TID251`. When a new input appears, add its contract
  file here first, then import it where it is read.
