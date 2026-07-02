<!-- pipeline-mode: single -->

# CLAUDE.md — src/controller/

Conventions for the controller layer. The marker above records which **pipeline mode** this
project was scaffolded with — `single` (one pipeline + thin main) or `multi` (intent dispatch).
Both modes are documented here so a `single` project can later upgrade to `multi` without
hunting for the pattern.

## Controller conventions (both modes)

- **`main.py` is thin and script-style — it defines no functions.** It imports the
  `config.startup` singletons, wires collaborators (the connection factory, `output_path`, the
  run-context dict, optional e-mail/webhook seams) into the pipeline, and calls `.run()`.
- **No data access, no rendering, no business logic in the controller.** Data access lives in
  `src/model/`, rendering in `src/view/`. The controller only *wires and sequences*.
- **The audit/summary write stays the last phase** of a run (new phases go before it).
- Phase methods/functions are bracketed by log lines so a run is self-describing.

## Mode: single (default)

One orchestrator, `controller/_pipeline.py` (`PipelineOrchestrator`), whose `run()` sequences
`_log_context → _open_engine → _read → _render → _write_summary → _notify`. `main.py` builds
it and calls `run()`. This is the right default — **don't add intent dispatch you don't need**
(YAGNI). Add phases as methods on the orchestrator.

## Mode: multi (intent dispatch)

When one service runs several distinct **purposes** off the same codebase (e.g. `send` /
`reconcile` / `notify`), it dispatches on a `PIPELINE_INTENT` env key instead of forking the
repo or branching inside `main`:

- **`controller/pipeline_common.py`** — the shared ports (`EmailHandler`, `WebhookNotifier`,
  `Pipeline`) and the intent-agnostic phases as plain **functions** (`log_context`,
  `render_report`, `write_summary`, `notify`, `log_elapsed`). Composition, not a base class.
- **`controller/pipeline_<intent>.py`** — one orchestrator class per purpose, each with the
  **same constructor contract** and a **zero-arg `run()`** (no leading underscore — these are
  discoverable, unlike single mode's `_pipeline.py`). Shipped examples: `pipeline_send.py`
  (read → render → persist → notify) and `pipeline_reconcile.py` (re-read the last run).
- **`controller/pipeline_dispatch.py`** — `resolve_intent(raw)` normalises the env value
  (case/accents/separators, bilingual aliases) and **fails loud** (`SystemExit(2)`) on a typo;
  `build_pipeline(intent, **shared)` constructs the matching orchestrator from a dispatch table.
- **`controller/main.py`** — thin: `build_pipeline(resolve_intent(PIPELINE_INTENT), …).run()`.
- Add a purpose = add a `pipeline_<intent>.py` + one entry in each table in `pipeline_dispatch`.

### Multi-intent + a "reconcile" purpose (re-reading the last run)

A reconcile/re-process intent consumes an **earlier** run's output. Do not reconstruct it from
human-facing artifacts (Excel/XML lose precision, the full field set and the routing keys).
Instead:

- **At produce time** (e.g. the `send` intent), append the **full payload** — every field the
  reconcile needs, plus its routing keys — to a dedicated values store, stamped
  `reference_date` + a per-send timestamp (reruns append, newest wins). A dynamic/wide schema
  (create-or-`ALTER ADD COLUMN`) absorbs an evolving field set without a migration.
- **At consume time**, read **DB-first** (latest stamp for the period). Only if absent, fall
  back to a **bounded, year-aware** scan of the dated output folders (cap the look-back; take
  the newest match; persist it to the DB for next time). Nothing within the cap → **fail loud**,
  never a silent empty.
- Reuse the producer's senders via `pipeline_common` so the re-send takes the **exact** delivery
  path (composition, DRY) — never a parallel copy. Unrouted items go to a never-dropped audit.

The shipped `pipeline_reconcile.py` keeps the baseline read simple (the prior summary JSON) to
illustrate the seam; wire the values-store + bounded-backfill above for a production reconcile.

### Combining multi-intent with the e-mail / webhook opt-ins

The e-mail opt-in patches the `CLS_EMAIL_HANDLER` sentinel in `main.py` and works in both modes.
The webhook opt-in's auto-wiring targets single mode's `main.py`; in multi mode, inject the
notifier into each `pipeline_<intent>` and call `pipeline_common.notify(...)` as the final phase
(the `WebhookNotifier` port and `notify` helper are already shared in `pipeline_common`).
