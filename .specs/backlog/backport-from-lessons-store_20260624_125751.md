# Backport backlog — global lessons store → templates (PR #34)

Second backport wave: applying the proven, generalizable lessons captured in the global
store `~/.claude/memory/lessons/` into the BlueprintX templates so every future scaffold
inherits them. Distinct from the 2026-06 wave
(`backport-from-cvm-perfil-mensal_20260607_071413.md`, all done, PRs #27–#32).

**Source of truth:** the global lessons store `~/.claude/memory/lessons/` + the proving
ground `~/dev/perfil_mensal_cvm`. **Branch:** `feat/backport-lessons-store` → PR #34
(blueprintx). Started v0.11.0; current v0.11.6.

> Status legend: `[ ]` to do · `[x]` done & verified in a scaffolded project (ruff + mypy +
> pytest, and where relevant `mkdocs build --strict` / end-to-end `make run`).

---

## templates/common — language-agnostic

- [x] `.gitattributes` pinning `*.sh text eol=lf` (Windows CRLF breaks bash).
- [x] `bin/lib/common.sh`: `ensure_dir()` UNC-safe mkdir (both byte-identical copies).
- [x] `bin/ship.sh`: bundle the working-tree `git_diffs/` offline-share payload.
- [x] `bin/commit.sh`: safe-commit helper (re-add hook-reformatted files, retry once, verify HEAD advanced).

## templates/python-common — Python lint/type gates

- [x] `mypy.ini` (pragmatic, src-layout) + mypy in pre-commit / `make lint` / `tasks.sh` / CI.
- [x] mypy invoked from `src/` (single base) + excludes `chassis`/`example_feature`/`typing` — fixes the DDD dual-root "found twice" + pre-existing chassis type-debt.
- [x] `.sqlfluff` + `.sqlfluffignore`, `.yamllint`, `.shellcheckrc`, `.hadolint.yaml`.
- [x] `bin/lint_{shell,sql,yaml}.sh` wrappers (skip-on-absent), shared by `make lint` + the new `lint-shell/lint-sql/lint-yaml` pre-commit hooks.
- [x] `ruff-format` pre-commit hook; `coverage-check` moved to the pre-push stage; `precommit` installs pre-push.
- [x] `ruff.toml`: `TID251` bans bare `pd.read_*` outside the `tabular_reader` seam (seam + tests + ORM `example_entity` exempt); bans constructing `FileContract` outside `config/contracts/`.
- [x] `.codespellrc` skips `htmlcov`/`coverage.svg`/`coverage.xml`/`*.diff`.
- [x] `test_cov_report` (HTML) + `test_cov_serve` recipes; dev deps `mypy`/`sqlfluff`/`yamllint`/`shfmt-py` in all 5 pyproject; vscode file-associations.
- [x] CI `tests.yaml` mirrors mypy + the lint gates; fixed stale `check_consistency.py` → `check_docstrings.py`.

## templates/python-common — utils seams + contracts

- [x] `utils/tabular_reader.py` — `read_table`/`read_query` requiring a `FileContract`, ending in `apply_dtypes`.
- [x] `utils/retry.py` (`retry_with_backoff`) + `utils/http_downloader.py` (stdlib urllib, SSRF-hardened — no new dep).
- [x] `utils/yaml_reader.py`, `utils/zip_extractor.py`, `utils/frames.py` (`map_with_default`), `utils/text.safe_str`.
- [x] `utils/decimals.parse_br_number_series` mirroring the scalar `_normalise_br_number` (+ parity test).
- [x] `utils/paths.py` enriched: `copy_into`, `date_tokens`, `resolve_input`/`resolve_input_glob` (absolute), `_latest_match`.
- [x] `utils/outlook_gateway.py` — Outlook seam (log-only off Windows) + dispatch flags + html-body helper.
- [x] `optional/`-style reference `config/contracts/` package (`__init__` aggregator + `example_source.py`), shipped to every service tier.
- [x] All shipped with green unit tests; wired into `copy_shared_utils` for the four service scaffolds. All shared `utils/` stay decoupled from the typing engine for cross-layout portability.

## templates/python-common — config layer

- [x] `config/env_config.py` env-wise selector (plain `inputs.yaml` default; opt-in `inputs_{dev,prd}.yaml` selected by `ENV`, fail-loud on unknown) + `startup.py` integration + tests.
- [x] Scaffold prompt `prompt_env_wise_config` / `apply_env_wise_config` in `bin/lib/common.sh`, wired into the four service tiers (lib-minimal has no config layer).
- [x] Runtime `@type_checker` applied across the config layer: `connection_db` (direct import), `env_config`/`startup` (TYPE_CHECKING/else shim for utils.typing vs chassis.typing).
- [x] `config/CLAUDE.md` (layer borders + contracts sub-package + type-checker policy).

## templates/python-common — MSSQL

- [x] `DB_ENCRYPT` / `DB_TRUST_SERVER_CERTIFICATE` support (ODBC Driver 18 defaults to encryption) with a `_normalize_odbc_bool` mapping `.env` booleans to `yes`/`no`, in both MVC factories (pyodbc string joined by `;`, SQLAlchemy URL params by `&`); documented in `.env.example`.

## templates/*/pyproject.toml — dependency floor

- [x] Bump the `stpstone` floor to `>=3.2.0` across the four service tiers. (Earlier attempt
  `28d3e77` was reverted as `6a9570f` because 3.2.0 was unpublished; it is now on PyPI, so the
  floor is applied for good and poetry version-solving resolves it.)

## templates/mvc-service-* — controller + docs

- [x] `controller/_pipeline.py` `PipelineOrchestrator` (`run` → `_log_context`/`_open_connection`(orm `_open_engine`)/`_read`/`_render`/`_write_summary`, `log_message`-driven, `try/finally` close/dispose) + thin no-functions `main.py` building it via DI; both MVC `CLAUDE.md` updated. Webhook opt-in still appends cleanly.
- [x] `src/model/CLAUDE.md` (ports/dtos "use only when shared" advisory) + `tests/CLAUDE.md` module-scoped expensive-fixture convention.
- [x] mvc-*/ddd-* `CLAUDE.md` data-handling guardrails (override re-normalisation, reject-nan-sentinel, keyed-merge-restrict-to-owner).

## all skeletons — docs site

- [x] mkdocs `exclude_docs` expanded (`superpowers/`, `checkpoints.md`, `blueprintx-lessons.md`) across all 5 skeletons.
- [x] mkdocs version label: `mkdocs_hooks.py` + `overrides/main.html` + `docs/javascripts/header-version.js` (single source in `templates/common/docs_version/`), wired into all 5 `mkdocs.yml`.

---

## In progress

- [x] **Email seam (`optional/email/`) mirroring the webhook seam.** A port + adapters +
  factory, opt-in like webhook. Port is **`EmailHandler`** (not `EmailSender`) — the concrete
  handler does more than send (download attachments, body/table extraction), so it is named as
  a handler that can grow. The **shared** Protocol holds only what every backend does (send),
  since SMTP is send-only; the Outlook handler exposes the extra read methods beyond the port.
  - [x] `EmailHandler` Protocol with `send_email` (shared across backends).
  - [x] `OutlookEmailHandler` (injects `utils.outlook_gateway.OutlookGateway`; delegates
    `send_email` AND `download_attachment` — the read capability SMTP lacks).
  - [x] `SmtpEmailHandler` (stdlib `smtplib`, send-only) + `NullEmailHandler` opt-out.
  - [x] `factory.build_email_handler(...)` selecting the backend via `EMAIL_BACKEND` (default outlook; blank/none → Null).
  - [x] mvc/ddd orchestrator depends on the `EmailHandler` port (was concrete `OutlookGateway`); default `main.py` wires none (opt-in adds it).
  - [x] opt-in scaffold prompt + conditional copy across the 4 service tiers (MVC → utils/email
    with chassis.email→utils.email rewrite + main.py sentinel swap injecting the handler into
    the orchestrator; DDD → chassis/email, no rewrite, no orchestrator).
  - [x] `.env`/`.env.example` keys (SENDER_EMAIL + EMAIL_BACKEND + SMTP_*).
  - [x] `EmailHandler` Protocol marked `@runtime_checkable` so the runtime TypeChecker accepts
    a concrete handler through the port (the proving ground avoided this by typing the param
    concretely; a port-typed param needs runtime_checkable).
  - [x] verified in all 4 service scaffolds: ruff + mypy clean; MVC (both backends) runs
    end-to-end; DDD factory imports resolve under chassis.email.
  - [x] unit tests for the seam (factory selection, unknown-backend raise, Null/SMTP
    validation, Outlook send+download delegation) — co-located in `optional/email/tests/unit/`,
    relocated by the scaffold into the project `tests/unit/` (MVC rewrites chassis.email→
    utils.email; DDD keeps it). Imports use the bare runtime root to dodge the dual-import-root
    isinstance trap. 8 tests pass under pytest in all 4 service tiers.

## Decisions to revisit (not blocking)

- [x] **`OutlookGateway` injected into the default `main.py`** — resolved by the email
  seam above: the orchestrator will depend on the `EmailSender` port (Outlook injected by
  default), and the seam ships opt-in like the webhook.

---

## How to consume this

Mirror of the live work on PR #34; the canonical lesson queue is `~/.claude/memory/lessons/`.
Tick the remaining boxes as the parked items unblock. Once every box is `[x]`, delete this
doc (per the docs/backlog convention).
