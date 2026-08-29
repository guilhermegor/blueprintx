# **Usage**

How to configure and run this service day to day.

> **See also:** [Architecture](architecture.md) for the layer layout · [Examples](examples.md)
> for task recipes.

---

## Running commands — Poe the Poet

Every command in this project is a **[Poe the Poet](https://poethepoet.natn.io/) task**,
declared in `poe_tasks.toml`. There is no `Makefile` and no `tasks.sh`.

```bash
poe                 # list every task, with a one-line description of each
poe lint            # run a task
```

### Getting `poe`

Poe is a **dev dependency**, so `bash bin/venv.sh` (or `poetry install --with dev`) puts it at
`.venv/bin/poe`.

| Route | Comes from | Use it when |
|---|---|---|
| `poe <task>` | the dev dependency, or a `pipx install poethepoet` | normal day-to-day work |
| `python -m poethepoet <task>` | any interpreter that has it installed | `poe` is installed but not on `PATH` |
| `poetry poe <task>` | the Poetry plugin, if you added it yourself | optional, supported, not required |

⚠️ The module is `poethepoet`, **not** `poe` — `python -m poe` fails.

If none of those resolve, `bash bin/poe_exec.sh <task>` tries all three in order and tells you
how to install it. **Scripts, hooks and workflows always use that wrapper**, never a bare `poe`,
for the same reason nothing here calls a bare `poetry`: whether a command is on `PATH` is a
property of the machine, not of this project.

### Tasks run inside the venv automatically

Poe finds the in-project `.venv` and runs each task under it, so you do **not** need to activate
anything or prefix commands with `poetry run`.

### Extra arguments pass straight through

Any tokens after the task name are appended to the underlying command:

```bash
poe unit_tests -k some_keyword    # pytest tests/unit/ -k some_keyword
poe unit_tests -x --lf            # stop on first failure, re-run last failures
```

That is why there is no `test_feat` task — the filter comes for free.

---

## Configure

Copy `.env.example` to `.env` and fill in the values (DB backend, credentials, any webhook URL).
`init` seeds `.env` automatically on a fresh checkout.

```bash
bash bin/venv.sh    # create the Poetry venv + install deps (this is what `poe venv` calls)
bash bin/ensure_env.sh && bash bin/precommit.sh   # the other two halves of `init`
```

⚠️ **Bootstrap runs the shell scripts directly, not `poe`.** Poe is a dev dependency, so it
lives inside the venv these commands *create* — it cannot be the thing that builds it. Once the
venv exists, `poe init` and `poe venv` work and do exactly the same thing; they are listed as
tasks so the command list is complete and discoverable.

That shell entrypoint is the second and last interface in this project. Everything else is
`poe`.

## Run

```bash
poe run             # runs the service entry point (src/.../main.py)
```

## Common tasks

```bash
poe unit_tests          # pytest tests/unit/
poe integration_tests   # pytest tests/integration/
poe lint                # ruff + mypy + codespell + pydocstyle + shell/sql/yaml gates
poe test_cov            # unit tests with coverage + badge
poe db_up               # start the database (Docker), ensure schema, apply migrations
poe docs_server         # serve these docs at http://0.0.0.0:8000
```

Run `poe` with no arguments for the full list.
