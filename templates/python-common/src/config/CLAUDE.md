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
- **`contracts/`** *(optional)* — `FileContract` value objects, one per input source, when
  the project opts into the data-contracts convention.
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
