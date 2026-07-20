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

## Ingestion reads pair with a provenance stamp

Every DataFrame produced by **ingesting from the internet** (a downloaded file or a webscrape)
carries a fixed set of provenance columns, appended after its source columns, so a datalake's
bronze layer is self-describing and drift-detectable. This is enforced, not merely advised:

- **The stamp seam** is `utils/provenance.py`: `hash_artifact(path)` (the I/O half — call it on
  the downloaded artifact **inside** the reader's temp-workspace block, before it is torn down)
  and `stamp_provenance(df, url, contract, content_hash, package_version)` (the pure half — a
  frame transform with no I/O, called **after** the contract check + dtype coercion). The six
  columns (`url`, `updated_at`, `source_key`, `package_version`, `ingestion_run_id`,
  `content_hash`) are named on `FileContract.PROVENANCE_COLUMNS`; a stamped frame's full shape is
  `cls_contract.output_columns` (= `tuple_required + PROVENANCE_COLUMNS`). They are **not** in
  `tuple_required` — that validates the *source* artifact, which never carries them.
- **The gate** is `bin/check_provenance.py` (wired into both `.pre-commit-config.yaml` and
  `.github/workflows/tests.yaml`, per the gate-parity rule): any `src/` module that **calls**
  `read_table(` must also reference `stamp_provenance`, so a file/scrape read cannot ship without
  its traceability columns. It keys on the call form `read_table(` on purpose — `read_query`
  (a DB read from *your own* database) is **not** internet-ingestion and is out of scope, and a
  contract module that merely *names* `read_table` in prose is a declaration, not a read.
- **`updated_at` is tz-aware UTC** (lossless, unambiguous). A sink that cannot store tz-aware
  timestamps normalises at the **warehouse load boundary**, never here and never via a per-reader
  flag — because it is one seam, changing that default later is a one-line change.

## Ground a contract's invariants in the real artifact, not just the schema

Before you declare a `FileContract` or add any validation to a reader, **download the real
artifact and measure the invariant you are about to assert** — not merely the column names.
"Percentages sum to 100", "this id is never null", "this key is unique", "this amount is
non-negative" are *hypotheses about the source*; a plausible-sounding one the data violates turns
a reader into a machine for false rejections.

- **Assert only what the artifact demonstrates.** A wrong column name raises loudly and
  immediately; a wrong *invariant* silently rejects valid production rows — or, used as an
  assumption rather than a check, silently corrupts a downstream aggregate. That asymmetry is why
  invariant grounding matters more than the (already-conventional) column-name grounding.
- **Where the data refutes the invariant, write the measured range into the docstring** (date,
  range, row count) so the *absent* check reads as a decision, not an oversight — nobody re-adds
  it. Worked example: a per-asset-type "share of net worth" column looks like it should sum to
  100% per group, but leveraged/short positions make real per-group totals run negative→>1000%;
  the check would reject valid rows. Conversely, a member verified one-row-per-key *is* a grounded
  basis for `merge(..., validate="many_to_one")`. Measurement is what tells you which you have.
- **Corollary — upstream class/name labels lie; read the URL.** A ported reader's class name may
  advertise a different source than the file it actually fetches. Confirm the artifact a reader
  pulls from its URL, not from what an inherited name claims, or you duplicate a reader or point
  it at the wrong file.
