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

> **`main` is protected — you never commit or push to it directly.** All changes land via a
> branch → Pull Request → merge (online), or `make new_branch` → `make git_merge_to_main`
> (offline). Cutting a release means creating a `vX.Y.Z` git tag; the Changelog page is then
> generated from that tag by `cz changelog` on the docs build.

This service is deployed, not published to a package index.

**With a GitHub remote (online):**
1. Land your work on the default branch through a Pull Request (CI is the merge gate).
2. Run the **Release** action (Actions → Release → *Run workflow*), entering the version
   (e.g. `1.4.0`). It creates the `v1.4.0` tag and a GitHub Release server-side — no direct
   push to protected `main`.
3. The docs deploy regenerates the Changelog from the new tag automatically.

**Without a GitHub remote (offline):**
1. `make new_branch NAME=feat/my-change` — branch off the default branch.
2. Do the work and commit (Conventional Commits).
3. `make bump_version` — runs `cz bump`: computes the next version from your commits, updates
   `pyproject.toml`, regenerates `CHANGELOG.md`, and creates the `vX.Y.Z` tag.
4. `make git_merge_to_main` — merges the branch into the protected default branch locally.
5. Preview the Changelog any time with `make changelog`.
