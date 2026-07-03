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
- [ ] (Future wave, NOT this branch) #1 calendar `DatesBRAnbima` — the LAST stpstone symbol.
      Three import sites, all the same calendar: `utils/dates.py` (ships to all 4 tiers) plus
      both `ddd-*/src/app/bootstrap.py`.
      **Plan: replace with a `wwdates` package (to be created).** `wwdates` will own the BR
      ANBIMA business-day / holiday logic; `utils/dates.py` will wrap it exactly as it wraps
      `DatesBRAnbima` today (same public surface — `is_working_day`, `add_working_days`,
      `delta_working_days`, …), so no downstream call sites change.
      - The two `bootstrap.py` uses are only `DatesBRAnbima().curr_datetime()` == stdlib
        `datetime.now(tz=ZoneInfo("UTC"))` — no calendar needed there; swap to stdlib and drop
        the import (frees DDD bootstraps from the calendar entirely).
      - Once `utils/dates.py` points at `wwdates`, delete `stpstone = ">=3.2.0"` from all 4
        service pyprojects and add `wwdates` — this is the one-line dep swap that finishes the
        dehydration.
