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

## Runtime type-checking does NOT decorate the config layer

The runtime `type_checker` / `TypeChecker` engine is applied to your **model / view /
controller** business code — **not** to config-layer modules (`startup.py`, `env_config.py`,
`connection_db.py`). This is deliberate, for two reasons:

- **Portability (shared files).** `startup.py` and `env_config.py` are copied into **both**
  layouts — MVC (`utils.typing`) and DDD (`chassis.typing`). A hard `from utils.typing import
  type_checker` would raise `ModuleNotFoundError` under DDD, so these stay decoupled from the
  engine exactly like the shared `utils/` helpers.
- **Nature of the layer.** `connection_db.py` is MVC-only (it *could* import `utils.typing`),
  but it is a thin lazy-import connection factory returning an opaque DB-API/SQLAlchemy object
  (already `ANN401`-exempt) — declarative glue, not the business code the runtime checker
  targets. Keeping the whole config layer undecorated is the consistent choice.

So a config module without `@type_checker` is correct, not an oversight — do not add the
import to the shared files (it breaks the DDD layout).

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
