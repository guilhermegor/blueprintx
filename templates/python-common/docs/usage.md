# **Usage**

How to configure and run this service day to day.

> **See also:** [Architecture](architecture.md) for the layer layout · [Examples](examples.md)
> for task recipes.

---

## Configure

Copy `.env.example` to `.env` and fill in the values (DB backend, credentials, any webhook URL).
`make init` seeds `.env` automatically on a fresh checkout.

```bash
make init        # seed .env, create the Poetry venv + install deps, install pre-commit hooks
# or, without make:
bash tasks.sh init
```

## Run

```bash
make run         # runs the service entry point (src/.../main.py)
# or:
bash tasks.sh run
```

## Common tasks

```bash
make unit_tests          # poetry run pytest tests/unit/
make integration_tests   # poetry run pytest tests/integration/
make lint                # ruff + mypy + codespell + pydocstyle + shell/sql/yaml gates
make db_up               # start the database (Docker), ensure schema, apply migrations
```

Run `make help` (or `bash tasks.sh help`) for the full list of targets.
