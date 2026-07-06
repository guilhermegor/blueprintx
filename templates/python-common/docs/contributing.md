# **Contributing**

Everything you need to develop, test, and ship changes to this service.

> **See also:** [Usage](usage.md) · [Architecture](architecture.md) · the repository's root
> `CONTRIBUTING.md` holds the authoritative branch/PR and commit-message policy.

---

## Setting up for development

The project ships both a `Makefile` and a parallel `tasks.sh` — use whichever suits your
machine (`make init`, or `bash tasks.sh init` when `make` is unavailable).

```bash
make init        # seed .env, create the Poetry venv + install deps, install pre-commit hooks
```

`init` composes `ensure_env` (seed `.env`), `venv` (create the Poetry virtualenv, install all
deps), and `precommit` (install the git hooks). Poetry is auto-installed if missing.

## Tests and linting

```bash
make unit_tests          # poetry run pytest tests/unit/
make integration_tests   # poetry run pytest tests/integration/
make lint                # ruff + mypy + codespell + pydocstyle + shell/sql/yaml gates
```

CI runs the same gates on every pull request; keep them green locally before pushing.

## Pull requests

1. Branch off the default branch following the prefix policy (`feat/…`, `fix/…`, …).
2. Fill out the PR template completely.
3. Ensure the CI checks (tests, lint, docs build) pass — they are the merge gate.

## Releasing

This service is deployed, not published to a package index. Bump the version with
`make bump_version LEVEL=<patch|minor|major>`, land it on the default branch via a PR, and
deploy per your environment's process. Keep [the changelog](changelog.md) current.
