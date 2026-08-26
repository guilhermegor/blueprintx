# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this template is

A **PyPI-ready Python library starter**. A clean, importable package with CI, pre-commit,
tests, docs, and PyPI + Test-PyPI release workflows ready to go. It is scaffolded by
BlueprintX into a new project directory; the scaffold replaces the `<project_name>` package
directory and the `pyproject.toml` placeholders via `envsubst`.

## Layout

```
src/<project_name>/
    __init__.py            # the public API surface (control it with __all__)
    main.py                # library core / entry point — rename or split as it grows
    _internal/             # PRIVATE — ships in the wheel, but not a public API
        utils/             # vendored helpers (dtypes, tabular_reader, retry/, http_downloader,
                           #   text, zip_extractor, br_identifiers, typing/)
        config/            # ALL private structural declarations (one config/CLAUDE.md maps them)
            contracts/     # FileContract declarations (one per input source)
            ports/         # private behavioural ABCs (hexagonal ports; ABCTypeCheckerMeta) — opt-in
            # schemas/     # (opt-in) Pydantic models mirroring an external standard
tests/
    unit/  integration/  performance/
```

**Public vs private.** Consumers import `<project_name>` (your core). Everything under
`<project_name>._internal` is vendored support code: it ships inside the wheel (so imports
resolve after `pip install`), but the leading underscore marks it off-limits — keep it out
of your public `__all__`. The internal imports are package-qualified
(`from <project_name>._internal.utils.dtypes import …`).

## Architecture

- **One public class per module/file.** The public class is named after the file
  (`user_service.py` → `UserService`). When helpers share no state and need no lifecycle,
  prefer **module-level functions** over a utility class. A private/shared base class gets
  its **own** `_`-prefixed file (`_base_reader.py`) — never share a module with a public
  class.
- **Separate I/O from logic**: pure functions in the core, side effects at the edges.
- Reach for a class only when there is **state + lifecycle**, **interface conformance**, or
  **dependency injection** — otherwise a module of functions is the right shape.
- **No redundant package-name subfolder.** When the package's whole purpose is one domain
  (e.g. `calendars`), do **not** nest a subfolder that repeats the package name
  (`src/<project_name>/<project_name>-ish/`) — the package name already conveys the scope. Keep
  public modules **flat** at `src/<project_name>/` (`src/<project_name>/calendar_br.py`), and put
  non-exported abstract bases / internals under `_internal/`.
- **On migration, reuse the target's own implementation.** When lifting code in from another
  repo, if this project already has an equivalent module (its own `_internal` typing engine, a
  helper), rewrite the imports to **this** project's version and discard the source's duplicate —
  never vendor a second copy (DRY). The scaffold's own `rewrite_internal_imports` embodies this.

## Conventions (inherited from `templates/python-common/`)

- **Ruff**: linter + formatter. Line-length 99, tab indent, double quotes, NumPy docstrings.
- **Pre-commit**: ruff, pydocstyle, codespell, commitizen, gitlint, unit + integration
  tests, coverage badge.
- **Tests**: `pytest` — `poe unit_tests`. Write
  pytest-style functions with fixtures, not `unittest.TestCase`.
- **Explicit column typing & Brazilian identifiers** — if the library touches pandas, type
  every DataFrame on load via `apply_dtypes` (`_internal.utils.dtypes`, never pandas'
  inference), route reads through `_internal.utils.tabular_reader`, and use
  `_internal.utils.br_identifiers` for CNPJ/CPF (alphanumeric-aware for the 2026 CNPJ).
- **No `.env`** — a distributable library has no runtime env to seed (unlike the service
  tiers), so none is shipped.
- **Logging via dependency injection** — never hard-import a logging backend in a helper;
  inject a logger (stdlib default), as `_internal/utils/retry/log_emitter.py`'s `LogEmitter`
  shows. The
  in-repo `logs.py` helper is **opt-in** at scaffold time; see `_internal/utils/CLAUDE.md`.
- **Every imported package is a direct dependency.** If a module `import`s a package, declare
  it in `pyproject.toml` — even when it is already installed transitively via another dep. A
  transitive presence is an accident of another package's tree and breaks silently the day that
  package drops or version-caps it. Run `poetry add <pkg>` for anything you import.

  **This is now enforced, not advised**: `bin/lint_deps.sh` runs `deptry` over `src/` in
  `poe lint`, the `lint-deps` pre-commit hook and CI. Its first run found the rule already
  broken in the tiers that ship it, which is the argument for the gate — the DDD tiers imported
  pandas in five `utils/` modules while declaring it nowhere, reaching them only through a
  business-day calendar that happens to depend on it. Two things worth knowing before working
  around it:

  - **A guarded import is still an import.** `try: import numpy / except ModuleNotFoundError:`
    degrades gracefully at runtime and changes nothing about the declaration — that pattern is
    why `numpy` went undeclared for as long as it did.
  - **Configuration lives in `pyproject.toml`'s `[tool.deptry]` block, never in a shared
    `deptry.toml`.** deptry takes its dependency list from the same file it takes its settings
    from, so `--config <other>` silently re-points it at a manifest that declares nothing.

## Three boundary rules, each with the test that applies it

The section above says WHERE a boundary goes. These three say when one is worth drawing at
all, and each is stated as a **test you can run on a decision** rather than as advice. All
three cost real rework in a proving ground before they were written down.

### 1. The seam knows the vendor; the callers do not

The rule that keeps a dependency swappable is usually mis-stated as *"hide the library"*, and
the naive reading of that does real damage: annotating the boundary with `Any`, erasing the
vendor's type, protects nobody. It removes the type checking and leaves the coupling exactly
where it was.

What actually makes a vendor swappable is narrower: **the seam imports and TYPES the vendor;
the callers import the seam.**

```python
# src/<project_name>/_internal/utils/http_downloader.py — the seam. It names the vendor,
# and it types it.
import requests

def download_file(str_url: str, path_dest: Path) -> Path: ...

# src/<project_name>/anything_else.py — the caller. It names the SEAM, and nothing else.
# ⚠️ Package-qualified, as every internal import in this tier must be: the helpers live
# inside the distributable package, so a bare `from utils…` resolves only by accident of
# sys.path and breaks once the wheel is installed.
from <project_name>._internal.utils.http_downloader import download_file
```

> **The test.** On the day the vendor is replaced, how many files change?
> One (the seam) means the boundary held. More than one means it never existed, however much
> the calling code avoided saying the vendor's name.

This is why `pandas` is `annotation_only` rather than banned outright: `-> pd.DataFrame` in a
signature survives no swap and blocks none — it is the vocabulary the layers agreed on.
`pd.read_sql(...)` is a call, and every file copied from the one that makes it inherits it.

### 2. Externalise text only when the destination has a DIFFERENT change cost

"Take the hard-coded text out of the code and put it in a YAML" reads as separation of
concerns and often is not. The question is never *whether the thing is text*. It is whether
the destination file **changes at a different rate, and by different people.**

A tracked YAML that only the author of the calling code ever edits has separated nothing: it
doubled the number of files that must change together, and added a parse step and a schema to
keep in sync.

> **The test.** Name the person who edits the new file WITHOUT touching the code, and name the
> occasion. If you cannot name both, the text belongs where it is used.
>
> Passes: an e-mail template an operations lead rewords at quarter end. Passes: a locale file
> a translator owns. Fails: a dict of column labels only the developer of that reader will
> ever change.

Measured on a 1,672-line e-mail-body module in a proving ground (2026-08-14), where the
externalised copy was edited exclusively alongside the code that read it.

### 3. Derive the boundary from the config that exists; never restate it

A bootstrap or preflight phase that needs to know *which file belongs to which category*
should **derive** that from the configuration already declaring it, rather than repeating the
list. The duplicate looks harmless the day it is written, because the two copies are identical
then. It is noticed only when they differ — and by then the question is which one is right.

```python
# Avoid — a second list that agrees with the first, until it does not.
LIST_REQUIRED = ["cad_fi.csv", "inf_diario.csv"]

# Prefer — the one declaration is the source; membership is derived from it.
LIST_REQUIRED = [cls_contract.str_filename for cls_contract in contracts.ALL]
```

> **The test.** Could the two copies disagree, and would anything fail if they did?
> If they can disagree silently, one of them must be computed from the other. This is the same
> rule `check_codespell_sync.sh` exists to enforce for the two `.codespellrc` files — that
> pair drifted in both directions, and the stale copy was the one shipping to projects.

## Releasing to PyPI

Two workflows ship under `.github/workflows/` (present only when a GitHub remote is set up):

- `release-test-pypi.yaml` — publish to **Test PyPI** first (`workflow_dispatch`).
- `release-pypi.yaml` — publish to **PyPI**, cut a GitHub release, then deploy the **versioned
  docs** with `mike deploy --update-aliases <X.Y> latest` (skipped for prereleases, so a suffixed
  version never moves `latest`).

**Docs are versioned via [mike](https://github.com/jimporter/mike)** and served from the
`gh-pages` branch — `docs.yaml` is a strict *build check only* and never deploys. Pages must be
set to "Deploy from a branch → gh-pages" via `poe enable_pages`, which waits until the first
release creates that branch. See `docs/contributing.md`.

Both gate on the version being greater than what is already published, build with Poetry,
and fall back to `twine` if `poetry publish` is unavailable. Configure these repository
secrets and a GitHub Environment named **`release`**:

- `PYPI_TOKEN` — a PyPI API token.
- `TEST_PYPI_TOKEN` — a Test PyPI API token.

## Extending this template

- Keep `src/<project_name>/` as the importable package root; grow the public API there.
- Add sub-packages as the project grows — do not dump everything into `main.py`.
- Mirror the test folder hierarchy to match the package structure.
- Drop `_internal/config/contracts` (and the pandas deps) if the library never reads
  tabular inputs.

## Project memory — thin root, lazy leaves (never `@`-imports)

This `CLAUDE.md` is a **thin index**: keep it scannable (what the project is, its structure, the
few commands that matter, the non-negotiable rules) and push domain detail into **leaf**
`CLAUDE.md` files that load **lazily** — a nested `CLAUDE.md` loads on directory entry; a
`rules/*.md` with `paths:` frontmatter loads on file touch. This template already ships leaves
(`src/*/CLAUDE.md`, `docs/CLAUDE.md`, `tests/CLAUDE.md`, `_internal/*/CLAUDE.md`, …).

**Never** wire those leaves through a `@.claude/<topic>.md` table. `@path` is an **eager import** —
Claude Code inlines every referenced file at session start, so a "Documentation" table of `@`-refs
loads *all* of them on *every* session: the structure looks lazy and behaves eager. Nested
`CLAUDE.md` and `paths:`-scoped rules are the only mechanisms that actually defer the load.

Corollary: a prose rule here cannot guard what `settings.json` / hooks auto-approve — put hard
guardrails in permissions or hooks, and keep `CLAUDE.md` for what config cannot express.
