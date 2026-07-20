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

## Import the sidecar schema descriptor when the source publishes one

Many open-data portals ship a **sidecar descriptor** beside the data (a data dictionary of field
names/descriptions/types/sizes) — CVM's `META/meta_<dataset>.txt`, a `.xsd`/`.dtd`, an OpenAPI
doc. When a source provides one it is the *authoritative* schema and does two jobs, both served by
the `utils/sidecar_metadata.py` seam:

- **Dev-time — define the contract from it.** Parse it (`parse_sidecar_metadata`) for the column
  names (and later types/scales) instead of sniffing the artifact header. It is more reliable, and
  it is also what lets a downstream lake diff "what the source says it publishes" against "what we
  loaded".
- **Runtime — persist it as a tracked artifact.** `fetch_sidecar_text(url, path_raw)` writes the
  descriptor to the bronze layer beside the data bytes, so the lake diffs it across runs and a
  schema change becomes **detectable and attributable** (rather than surfacing only as "a transform
  broke").
- **Tolerate absence — it is a first-class case.** `fetch_sidecar_text` returns `None` (never
  raises) when the source publishes no sidecar; the reader then falls back to inferring the
  contract from the real downloaded artifact. Never *skip the check* — fall back to it.
- **The seam is generic; the locator is the source-specific part.** `cvm_meta_url(base, key)` is
  the shipped **reference** locator (`<base>/META/meta_<key>.txt`); write a sibling `str → str`
  locator for another source and pass its result to `fetch_sidecar_text`. The download transport is
  injectable (defaults to the one `http_downloader.download_file` seam), so tests mock at that
  boundary and the network guard stays satisfied.

## Pin every contract to a source-published oracle

A `FileContract` is only *correct* if it is checked against something **the source produced** —
never against itself. The failure mode is a tautology: a wrong contract passes every test, because
the contract, the reader's assertion, and a hand-written fixture all encode the *same belief*.
Adding more unit tests inside that loop adds agreement, not truth. So:

- **Generate the contract's columns from the real bytes; never transcribe them.** The oracle is,
  in priority order: (1) the source's own spec if it publishes one (a sidecar `META`, an
  `.xsd`/OpenAPI doc — see the sidecar-metadata section), else (2) the real artifact's **header**,
  committed verbatim as a tracked fixture under `tests/fixtures/`. Then assert
  `contract.tuple_required == header_from_fixture` — both steps, not just the first.
- **Header-only fixtures — never commit real data rows** if the artifact can carry personal data
  (a CPF/CNPJ column). The header line gives the full anti-tautology benefit with zero PII.
- **A spec often lacks column *order*** (an alphabetical `META` vs the real file). Use the spec for
  **names/types**, the real header for **order** — complementary, not interchangeable.
- **Tooling.** `bin/pin_contract_oracle.py` extracts the header tuple from a downloaded artifact
  (and optionally writes the `tests/fixtures/<key>__header.csv` fixture) so the pin is *generated*,
  mechanically, not typed by hand. `tests/unit/test_contract_oracle_example.py` is the copyable
  worked example of the `contract.tuple_required == oracle` assertion.

### Two layers, and why the drift job must never gate

| layer | when | catches | gates? |
|---|---|---|---|
| pinned header/spec fixture | PR-time, **offline** | **you** writing the contract wrong | ✅ yes |
| scheduled drift job | weekly, **online** | **the source** changing it after you shipped | ❌ **never** |

The fixture proves the contract matched the day it was written; only a job that looks again can
know the source changed yesterday. But that job **must never fail CI or gate a release**: a network
test contradicts the socket-blocking `conftest` guard, "the source is down" and "our contract is
wrong" are indistinguishable as a red check, and an external host on the release path has silently
skipped a publish before. So drift → **open (or update) an issue**, never fail — and **dedupe**, or
a weekly job that files a fresh issue every run becomes noise that gets switched off.

### Subset vs full-column contracts — the drift job must know which it has

`tuple_required` means **"the file must contain at least these"**, not "these are exactly the
columns". So every contract is one of two kinds, and the choice should be **conscious per source**:

- **Subset** (`bool_full_column=False`, the default) — require the *key* columns and let the rest
  flow through as typed text. Deliberate and legitimate, but it opts out of the full-header
  pinned-oracle guarantee.
- **Full-column** (`bool_full_column=True`) — generated from the whole published header; the
  pinned-oracle kind.

This distinction is load-bearing for the drift job, because the two directions are **not**
symmetric:

| direction | subset contract | full-column contract |
|---|---|---|
| a **required** column vanished from the source | ✅ always drift | ✅ always drift |
| the source has a column the contract doesn't list | ❌ **noise** (most columns aren't required) | ✅ drift (the source added a field) |

`check_contract_drift.py` gates the second direction on `bool_full_column` for exactly this
reason. Flagging it unconditionally reports every non-required column as a finding — a real run of
this pattern elsewhere opened its first issue with ~122 false positives out of 123, and a job that
cries wolf 122:1 is worse than no job, because nobody reads the 123rd week's issue. A fetch failure
is likewise **not** drift (the source may be down, or the current period may not be published yet)
— it is logged as a note, never written into the issue-opening report.

The seam: `config/contract_oracles.yaml` is the registry (`source_key → {url, sep, encoding}`,
**empty by default**); `bin/check_contract_drift.py` compares each shipped contract's columns
against the live header and **always exits 0** (self-skips to success when the registry is empty —
a check that never reports would block nothing, but this one is a *reporter*, not a gate); the
`contract_drift.yaml` workflow runs it weekly (and on manual dispatch, **never** on PR/push) and
opens/updates one deduplicated issue when drift is found.
