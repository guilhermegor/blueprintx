# **Contributing**

Everything you need to develop, test, and release this library.

> **See also:** [Usage](usage.md) · [API Reference](api.md) · the repository's root
> `CONTRIBUTING.md` holds the authoritative branch/PR and commit-message policy.

---

## Setting up for development

The project ships both a `Makefile` and a parallel `tasks.sh`, so use whichever suits your
machine — **`make init`**, or **`bash tasks.sh init`** when `make` is unavailable (e.g. a stock
Windows shell).

```bash
make init        # seed .env, create the Poetry venv + install deps, install pre-commit hooks
# or, without make:
bash tasks.sh init
```

`init` composes `ensure_env` (seed `.env`), `venv` (create the Poetry virtualenv, install **all**
dependencies including dev + docs), and `precommit` (install the git hooks). Poetry is
auto-installed if missing.

## Tests and linting

```bash
make unit_tests          # poetry run pytest tests/unit/
make integration_tests   # poetry run pytest tests/integration/
make lint                # ruff + mypy + codespell + pydocstyle + shell/sql/yaml gates
```

CI runs the same gates on every pull request; keep them green locally before pushing.

## Verifying the built package

Before opening a release PR, confirm the wheel actually builds and imports — this catches
packaging mistakes (a missing `__init__`, an unshipped `_internal/` subpackage) that source-tree
tests never surface:

```bash
make install_dist_locally    # python -m build → install → smoke-import → report the built wheel
```

## Publishing the documentation (versioned, via mike)

The published site is **versioned**: a consumer pinned to an older release reads *that
release's* docs, not HEAD. [mike](https://github.com/jimporter/mike) maintains the version tree
on the `gh-pages` branch and MkDocs-Material renders the version dropdown.

Two workflows split the work:

| Workflow | Trigger | What it does |
|---|---|---|
| `Docs - Strict Build Check` (`docs.yaml`) | every push + PR | `mkdocs build --strict` only — catches broken links/nav before a release. **Never deploys.** |
| `Release to PyPI` (`release-pypi.yaml`) | manual release | after the PyPI publish succeeds, deploys the released version with `mike deploy --update-aliases <X.Y> latest` |

Because the deploy runs **after** publishing, the site only ever advertises versions that
actually shipped. Notes:

- **Granularity is `X.Y`** — `1.4.2` and `1.4.7` share the `1.4` entry; the `latest` alias
  always tracks the newest release and is the default landing version.
- **Prereleases never move `latest`** — a version with a suffix (`1.2.3rc1`) builds and
  publishes, but the docs deploy job is skipped.

### One-time Pages setup

mike serves from the **`gh-pages` branch**, so Pages must be set to *Deploy from a branch →
gh-pages*. The workflow's `GITHUB_TOKEN` cannot change that (it is a GitHub App token without
repo-admin rights), so do it with your own `gh` auth:

```bash
make enable_pages          # or: bash tasks.sh enable_pages
```

This already runs inside `make init` / `bash tasks.sh init`, and is **idempotent and
non-blocking** — it warns and continues if `gh` is absent/unauthenticated, no remote resolves,
or you are not a repo admin (a fork), so it never breaks `init`.

**Ordering matters:** the `gh-pages` branch does not exist until the first release deploy
creates it. Until then `enable_pages` deliberately leaves Pages untouched (so the site is never
pointed at an empty branch) and tells you to re-run it. So: cut the first release, then run
`make enable_pages` once. Manual alternative: *Settings → Pages → Build and deployment →
Source: Deploy from a branch → `gh-pages` / `/`*.

## Pull requests

1. Branch off the default branch following the prefix policy (`feat/…`, `fix/…`, …).
2. Fill out the PR template completely.
3. Ensure the CI checks (tests, lint, docs build) pass — they are the merge gate.

## Releasing

Releases are **tag-driven and secret-free** when the project is connected to a GitHub remote:

- The version is the **git tag** (via `poetry-dynamic-versioning`); `pyproject.toml` holds a
  `0.0.0` placeholder. Do not hand-edit it. Trigger a release from the Actions tab
  (`Release to PyPI` / `Release to Test PyPI`, `workflow_dispatch` with the version), or by pushing
  a `vX.Y.Z` tag.
- The release workflow runs the **full test suite** as a hard gate, builds with `python -m build`,
  and publishes via **OIDC trusted publishing** (`pypa/gh-action-pypi-publish`) — no stored
  `PYPI_TOKEN`.
- The changelog is regenerated from tags at release/build time (`make changelog` locally); CI never
  commits `CHANGELOG.md` back to the protected default branch.

### Maintainer setup — trusted publisher (one time, before the first release)

Register a **trusted publisher** on **both** [pypi.org](https://pypi.org) and
[test.pypi.org](https://test.pypi.org). Every claim must match the workflow exactly or the upload
fails with an opaque `invalid-publisher`:

| Claim | Value |
|-------|-------|
| Owner / repository | your GitHub `<owner>` / `<repo>` |
| Workflow filename | `release-pypi.yaml` (PyPI) / `release-test-pypi.yaml` (Test PyPI) |
| Environment | `release-pypi` / `release-test-pypi` |
| PyPI **Project Name** | must equal the distribution name (`name` in `pyproject.toml`) |

For the very first upload the project does not exist yet — register a **pending publisher** at the
account level (not under an existing project's settings). Publishing from a laptop instead of CI is
the one case that still needs an API token; OIDC works only from GitHub Actions.

### Choosing publish targets

The scaffold wires the release workflows for the official public registry (PyPI) and a staging
registry (Test PyPI). To publish to a **private / non-official** source instead — a git source
(`pip install git+https://…`), a private PEP 503 index, or (for ecosystems that support it) GitHub
Packages — wire the consumer-side source in `pyproject.toml` with an explicit-priority guard
against dependency confusion (`poetry`'s `priority = "explicit"`; `pip --index-url`, never
`--extra-index-url`).
