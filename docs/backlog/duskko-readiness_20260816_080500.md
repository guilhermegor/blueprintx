# Duskko readiness — Tier A bundle

> **DONE 2026-08-16 — kept as a record.** Everything here was delivered in PR #170 (squash
> `ac069c3`) and published in **v0.15.3**. For *what still remains*, read
> **`duskko-blockers_20260816_110000.md`**, not this file.
>
> ⚠️ A priority changed during the session and is worth recording in writing, because the line
> below still lists **#127** as Tier A: it was **downgraded**. #127 covers the index blocked
> *entirely*; the field evidence (Werner's box) showed the index blocked *partially* — which is
> **#165**, already delivered. Do not resume #127 as if it were urgent.

**Created:** 2026-08-16 08:05
**Branch:** `fix/158-duskko-readiness-bundle`
**Hard deadline:** 14:00 on 2026-08-16 (start of the duskko project with Werner)

## Why this bundle exists

Duskko will be scaffolded from **`mvc-service-native-db`** and does collection (Treasury API,
replacing the queries in `contexto_duskko/config/consultas_sql/`), processing and persistence in
SQLite. Per the `template-fix-does-not-reach-already-scaffolded-projects` lesson (#109), **a
fix that lands before `make new` propagates for free; after it, it requires a manual
backfill**. So the selection criterion isn't "how many issues do I close", it's "which ones
touch the surface duskko uses on day 1".

Confirmed target environments: **Windows + XP's TLS proxy** *and* **Linux/WSL publishing to
PyPI** — both count, so the corporate-environment items stay in scope.

**Out of scope by decision:** duskko's `make new` is not done here. The user decides when to
stop developing on BlueprintX and scaffold.

## Scope (ordered by blocking × cost)

- [x] **#158** `default_stages` in `.pre-commit-config.yaml` — every gate ran 2x (commit + push)
- [x] **#143** `tabular_reader`: `any()` on an empty series + `astype(str)` not NA-safe
      — negative control: 2 failed on the old code → 9 passed on the fixed one. Extra finding:
      on **pandas 3** `.astype(str)` does not produce `"nan"` (pandas 2's behavior), it lets
      `float nan` reach the validator and beartype raises `TypeError`. The defect is a crash,
      not a silently wrong validation. `safe_str` fixes both regimes.
- [x] **#165** a partially blocked (403) PyPI index aborts the whole `init` — **field evidence
      from Werner's box (2026-08-16)**; pruned by `DB_BACKEND` + incremental install.
      The pruning test caught a bug of mine before the commit: `_read_env_var` resolves `.env`
      relative to **CWD**, so every backend read `sqlite`. Anchored to `$PROJECT_ROOT/.env` —
      same family as the `resolve-config-paths-to-absolute` lesson (#122).
- [x] **#147** ingestion-reader robustness — **2 of 3 lessons delivered**: field names
      normalized at the read boundary (`.strip()`) and `decode_positional_payload` with
      asymmetric width handling. The third (fixture envelope) is a test convention and belongs
      to #152/#124, not to the seam.
- [x] **#166** the `read_table` JSON branch broke the "read as text" guarantee —
      `pd.read_json` coerces even values published in quotes (`"1000.50"` -> `1000.5`,
      `"007"` -> `7`). A parse boundary, hits directly on JSON API money data.
- [x] **#115** emoji in `bin/check_*.py` breaks the gates on Windows cp1252 — 8 files, 41
      non-cp1252 characters. Fixed at the I/O seam (UTF-8 reconfigure), not by removing the
      glyphs. Negative control: 2 failed without the fix, 9 passed with it.
- [x] **#114** `get_corporate_ca.sh` narrowed the TLS trust store instead of merging into it —
      now reads the OS trust store (`ssl.enum_certificates`, no network and no verification
      disabled) and `wire_corporate_ca` builds `bin/ca_bundle.pem` as a UNION (certifi + host
      bundle + corporate CA). Removed the in-place certifi append and `PIP_TRUSTED_HOST`.
- [x] **#160** `startup.py` built the LOGGER after a fallible resolution — explicit fragility
      gradient, failure caught and reported to log + stderr with exit 2, order guard via
      `ast`. Negative control: 2 failed on the old form.
- [ ] **#127** offline wheelhouse for the pip fallback (blocked index exits 0 with an empty
      venv) — **priority dropped**: #165 resolved the acute Nexus failure (403 per package).
      The wheelhouse covers the index blocked entirely, which isn't what Werner's box shows.

## Vendor boundary (owner's request, mid-session)

- [x] `utils/frames.from_cursor` + `model/example_entity` in the **native-db** tier stop
      calling the pandas API; `pd.DataFrame` stays only as an annotation. Real scaffold: 203
      passed, lint clean.
- [x] **#171** the gate that makes this mechanical — `bin/check_layer_imports.py` +
      `.layer-policy.yaml` per tier + 10 tests + hook/CI/scaffolds wiring. Proven across 4
      shapes: top-level vendor call fails; vendor call inside a function under
      `try/except ImportError` fails (message names the evasion); `pd.read_sql` fails;
      `pd.DataFrame` only as an annotation passes. Real scaffold: **213 passed**.
- [x] **#172** **ORM** tier: `example_entity` read via `pd.read_sql` (banned by `ruff.toml`
      itself) and the file was exempted from `TID251` via `per-file-ignores` — the exemption
      sat in the file `CLAUDE.md` tells you to COPY, so it exempted the pattern. Now reads
      through the ORM session and builds the frame with `utils.frames.from_records`; exemption
      removed; both `CLAUDE.md` claims corrected.
- [x] CodeRabbit review on PR #170 collected and resolved: 4 Major (2 of them would have
      reintroduced defects already fixed this session) + 2 minor.
- [x] Kanban cards fixed — the hook only moves the card of the issue that started the branch,
      and I bundled 8 into one branch.
- [ ] **#173** apply the PR gate to BlueprintX itself (`required_conversation_resolution`,
      required checks, GitGuardian) — ~~measured: nothing blocks a merge today~~ **stale.**
      Measured via the API on 2026-08-22: `required_conversation_resolution=true` and **15**
      required status checks on `main` (threads, spell, shellcheck, actionlint, mkdocs, version
      sync, meta, copy-lists and the 7 scaffold+lint+test jobs). The refused merge was **proven
      in PR #219 with a negative control**: red gate + red GHAS = `BLOCKED`; green gate + red
      GHAS = `CLEAN`, so GHAS does not block and the gate is the cause. Only **GitGuardian**
      remains (#153/#155) — see `pr-gate-blocks-merge_20260817_104500.md`.

## Opened during the session (outside Tier A, logged for later)

- **#167** cyclomatic-complexity gate in python-common (1 test / 2 modules) — with measurement
- **#168** the same gate explored for the ts-* layouts

## Outside Tier A (don't touch duskko on day 1)

ts-lib (#132–#136), docs gates (#159, #130, #141), PR-gate (#145), GitGuardian
(#153/#155/#129), and the 6 issues opened this session that remain unimplemented
(#159 through #164).

## This session's audit record

Swept lessons in `~/dev`, `~/github` and `~/.claude` cross-checked against open issues. Waves
1+2 (#113–#130, #143–#156) had already drained the corpus by 2026-08-09 and stamped the
lessons with `blueprintx#N`; 14 lessons captured afterward remained, which became
**#158–#164**. The bidirectional mirror↔store diff turned up 3 anomalies, all known and
benign.

Folds decided (no new issue, same surface delivered):
- skipping build output in `.codespellrc` → extends **#126**
- empty recipients on send → acceptance criterion of **#121**
