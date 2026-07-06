# **Contributing**

How to contribute to BlueprintX itself (the scaffolding tool).

> **See also:** the repository's root `CONTRIBUTING.md` holds the authoritative branch/PR and
> commit-message policy · [CLI Reference](cli-reference.md).

---

## Development setup

```bash
make init          # bootstrap the venv + install pre-commit hooks
make lint          # run all pre-commit hooks across the repo (mirrors CI)
```

The root repo's pre-commit mirrors `.github/workflows/scaffold-checks.yml`: the shared checks
live in `bin/ci/*.sh` and both the workflow and the hook call them — one home per check.

## Adding a new skeleton

1. Create `templates/<name>/` with the skeleton's files.
2. Add a `skeleton.meta` descriptor (`language`, `display_name`, `description`, `scaffold`).
3. Write a scaffold script under `bin/scaffold/`.
4. The interactive menu discovers it automatically — no change to `blueprintx.sh`.
5. Add the install/usage notes to `README.md` and a docs page under `docs/`.

## Shared template sources

`templates/python-common/` (shared Python tooling), `templates/ts-common/` (shared TypeScript
tooling), and `templates/common/` (language-agnostic assets) are the single sources of truth —
change them there and every skeleton inherits the change on the next scaffold run.

## Pull requests

Branch off `main` using the CONTRIBUTING prefix policy (`feat/…`, `fix/…`, …), keep `make lint`
green, and fill out the PR template. Direct commits to `main` are blocked by pre-commit.

## Releasing

The version is the git tag — cut a release from the **Release** GitHub Action (enter the
version once). See the [FAQ](faq.md#how-is-blueprintx-itself-versioned).
