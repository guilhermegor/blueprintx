# Dehydrate stpstone from BlueprintX templates

Branch: `feat/dehydrate-stpstone-utils`

Reduce coupling to the large `stpstone` umbrella dependency by vendoring / replacing the small
pieces the templates actually use. Of the 7 symbols originally imported, **6 are now removed**;
only #1 (the BR calendar) remains external, so the `stpstone` dep line stays in the 4 service
pyprojects until a later wave dehydrates the calendar too.

## What shipped (all verified: 172 files compile, ruff check+format clean, logging tests pass)
- [x] **#2/#3 logs** → consolidated into ONE `utils/logs.py` (`CreateLog` + `log_message` +
      `initiate_logging`), vendored faithfully (frame-walk kept), project `TypeChecker` via shim,
      `curr_datetime()` → stdlib `datetime.now(tz=ZoneInfo("UTC"))`. Deleted `create_logs.py`,
      `init_setup.py`, `loggers.py`. Swept 10 consumers `utils.loggers` → `utils.logs`.
- [x] **#4 json** → inline stdlib `json.dump` at the 4 pipeline sites (dropped the meaningless
      `bool_ok`); deleted the `json_writer.py` seam (stdlib needs no coupling seam).
- [x] **#5 yaml** → inline stdlib `yaml.safe_load`; deleted `yaml_reader.py`. Fixed a latent bug:
      the scaffold appended `reading_yaml(...)` to `startup.py` after the import was removed →
      NameError; the 4 scaffold scripts now emit `yaml.safe_load(...)`. Declared `pyyaml` dep.
- [x] **#6 teams** → `pymsteams` directly (as stpstone's `WebhookTeams` did internally); declared
      `pymsteams` dep in the 4 service pyprojects.
- [x] **#7 outlook** → vendored `DealingOutlook` INTO `utils/outlook_gateway.py` as private
      `_com_*` functions (lazy `win32com`, so the module stays Linux-importable); merged the
      client+gateway into one module. Replaced 3 stpstone helper calls with stdlib
      (`in` / `.split(".")[-1]` / `os.path.exists`). Added the `get_body_content` capability.
      Declared `pywin32` as a Windows-only dep. Deleted the interim `outlook_client.py`.
- [x] Tests: merged `test_logs.py` (seam + CreateLog); deleted `test_loggers.py`,
      `test_create_logs.py`, `test_json_writer.py`.
- [x] Docs: tier `CLAUDE.md` ×4, `python-common/CLAUDE.md`, `docs/architecture.md` ×2,
      `docs/py-mvc-*.md` ×2 — "calendars/parsers come from stpstone" → "BR calendar only";
      `utils.loggers` → `utils.logs`; `loggers.py` row → `logs.py`.

## Remaining
- [x] Capture the generalizable lesson (global store + `docs/blueprintx-lessons.md`).
- [x] `run act` on the scaffold-checks workflow before pushing (per act-first rule) — green
      end-to-end (make lint clean tree, mypy + docstrings, 111 unit tests); caught 3 scaffold
      drifts fixed in commit `60eb6c6`. Shipped as PR #37 (v0.12.1).
- [x] **DONE 2026-07-20 (issue #94, branch `feat/94-dehydrate-stpstone-wwdates`)** — #1 calendar
      `DatesBRAnbima`, the LAST stpstone symbol, dehydrated. **stpstone is now fully gone from the
      templates** (`git grep stpstone -- templates/` → 0 hits). What shipped:
      - `utils/dates.py` re-pointed at **`wwdates.br.anbima.DatesBRAnbima`** — a genuine 1:1 map
        (same class name, all 6 wrapped methods, positional calls), so the wrapper body and every
        downstream call site are unchanged. Verified live in a scaffolded DDD tree.
      - Both `ddd-*/src/app/bootstrap.py`: `DatesBRAnbima().curr_datetime()` → stdlib
        `datetime.now(tz=ZoneInfo("UTC"))`; calendar import dropped entirely.
      - `stpstone = ">=3.2.0"` → `wwdates = ">=0.1.0"` in all 4 service pyprojects; residual
        doc/comment mentions scrubbed (test_dates, mypy.ini, webhook notifiers, tier CLAUDE.md ×4,
        architecture.md ×2, logs.py provenance line).
      - ⚠️ **Latent bug surfaced + fixed:** `test_outlook_gateway.py` (ships to all 4 service tiers)
        imports `pytest_mock`, but the DDD pyprojects never *declared* `pytest-mock` — it was only
        present because stpstone transitively pulled it. Removing stpstone exposed it; added
        `pytest-mock` to both DDD dev groups (the MVC tiers already declared it). This is the
        `never-build-on-transitive-dependency` lesson, caught by the CI harness.
      - **Verified:** harness green on both DDD tiers + MVC-native; live wwdates wrapper call
        correct; `git grep stpstone -- templates/` = 0.
