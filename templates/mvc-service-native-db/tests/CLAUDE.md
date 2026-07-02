# CLAUDE.md — tests/

Conventions for writing tests in this project. Read this before creating or editing any
test file. The goal: an AI (or human) can add a new test module that passes lint and CI on
the first try.

## Layout

```
tests/
  unit/          # fast, isolated tests — mock at I/O boundaries (DB, network, filesystem)
    conftest.py  # shared fixtures (e.g. df_sample)
    test_*.py    # one module per unit under test
  integration/   # tests that touch a real DB/API/filesystem
  performance/   # benchmarks, load, memory
```

Run them with `make unit_tests` (`poetry run pytest tests/unit/`) or `pytest tests/unit/`.

## Imports

`pytest.ini` sets `pythonpath = . src` — **both** the project root and `src/` are on the
path. For most tests, import the code under test through the `src` package:

```python
from src.view.report_renderer import RenderToExcel
from src.model.example_entity import ExampleEntity
```

### The dual-import-root trap (TypeChecker-guarded classes)

Because both roots are on the path, a module is importable **two** ways — `src.utils.x`
(via the root) and `utils.x` (via `src/`) — and Python treats them as **distinct module
and class objects**. This bites when a `TypeChecker`-guarded class is constructed in a test
and handed *another* src-class instance: if the two are imported via different roots,
`isinstance` fails with the baffling `X must be of type Foo, got Foo` (same name, different
object).

Rule: when a test wires together two src classes and at least one is `TypeChecker`-guarded,
import **both** via the **bare runtime root** — the way the app actually runs:

```python
from utils.paths import resolve_path            # NOT src.utils.paths
from view.report_renderer import RenderToExcel  # NOT src.view.report_renderer
```

The plain `from src.X import …` convention is fine for classes whose constructor takes only
stdlib types / paths (no cross-src instances to `isinstance`-check).

Order imports as `ruff.toml` enforces (`force-sort-within-sections = true`) — within each
group, `import X` and `from X import Y` are sorted together by module name, stdlib then
third-party then first-party, two blank lines after the import block:

```python
from pathlib import Path

import pandas as pd
import pytest
from pytest_mock import MockerFixture

from src.view.report_renderer import RenderToExcel
```

## Formatting (must pass `make lint`)

- **Tabs, not spaces** — `ruff.toml` sets `indent-style = "tab"`. The most common lint
  failure is a 4-space-indented test file. Indent every level with one tab.
- **Double quotes** everywhere (`quote-style = "double"`).
- **Type annotations on every function**, including `-> None` on tests and fixtures
  (flake8-annotations is strict).
- **NumPy docstrings** on every test and fixture. **Never** append `, optional` to a
  parameter's type field — write the type exactly as annotated (`tmp_path : pathlib.Path`,
  not `tmp_path : pathlib.Path, optional`); the docstring type checker runs on tests too.

## Structure of a test module

Use comment-banner sections in this order (omit a section if empty):

```python
# --------------------------
# Module Utilities   # plain helper functions (no fixtures)
# --------------------------

# --------------------------
# Fixtures           # @pytest.fixture definitions (or put shared ones in conftest.py)
# --------------------------

# --------------------------
# Tests
# --------------------------
```

## Test rules

- **Name**: `test_<unit>_<scenario>_<expected_outcome>` — e.g.
  `test_render_missing_parent_dir_creates_it`.
- **One behaviour per test.** Assert a single outcome; split scenarios into separate tests.
- **Mock at the boundary, not inside business logic.** Patch the filesystem, DB cursor/session,
  HTTP client, or webhook — never the function under test. Use `pytest-mock`'s `mocker`
  (`mocker.patch`, `mocker.patch.object`); use `tmp_path` for real-but-disposable files.
- **Deterministic.** No real network, no real clock dependence, no unseeded randomness.

## Expensive shared setup: render once, share via a scoped fixture

When several tests assert on **different facets of one expensive-to-build artifact** (a
rendered workbook, a built report, a large parsed frame), build it **once** with a
module- or session-scoped fixture instead of rebuilding it per test:

```python
@pytest.fixture(scope="module")
def path_rendered(tmp_path_factory: pytest.TempPathFactory) -> Path:
	"""Render the report once for the whole module (expensive build shared)."""
	path_out = tmp_path_factory.mktemp("render") / "report.xlsx"
	RenderToExcel().write(df_sample(), path_out)
	return path_out
```

The smell this fixes is "redundant expensive setup masquerading as independent coverage" —
N tests each re-running the same costly build. **Share only when the tests inspect one
artifact**; if a test needs a *different* input/state, give it its own (function-scoped)
fixture. Never share a **mutable** object across tests at module scope (one test's mutation
leaks into the next) — share the immutable result (a path, a frozen frame copy).

## Examples in this folder

- `unit/test_report_renderer.py` — the canonical sample: real-file tests via `tmp_path`,
  a round-trip assertion, and one boundary-mocked test via `mocker`.
- `unit/conftest.py` — the `df_sample` fixture shared across the unit suite.

## Testing the other layers

- **Model** (`src/model/`): for the native variant, pass an in-memory `sqlite3.connect(":memory:")`
  connection to `ExampleEntity` and assert on the returned DataFrame; for the ORM variant, build
  an in-memory engine (`sqlalchemy.create_engine("sqlite://")`). These are integration-flavoured —
  put them in `tests/integration/` if they spin up a real engine.
- **Controller** (`src/controller/main.py`): it is a script-style module with import-time side
  effects (it runs the pipeline on import). Prefer testing the model and view directly rather than
  importing the controller; if you must, mock `model`/`view` at the boundary first.

## Testing shell scripts

A bash script in `bin/` has no conventional unit test, so map the tests-with-every-change rule:

- **Unit gate** = `shellcheck --severity=warning --exclude=SC1091` + `bash -n` (already run by
  `bin/lint_shell.sh` and the `lint-shell` pre-commit hook). When a shell change ships without a
  Python unit test, say so explicitly — it is a documented choice, not an omission.
- **Integration** = invoke the script via `subprocess` and assert observable behaviour (exit
  code, a created file/dir, a status line). Resolve bash with `shutil.which("bash") or "bash"`,
  build a constant trusted argv, scope-ignore bandit `S603` with a one-line reason, and self-skip
  when a dependency is unavailable offline.

`tests/integration/test_bin_scripts.py` is the shipped reference example (covers the shared
`bin/poetry_exec.sh` and `bin/precommit.sh` seams). See also `bin/CLAUDE.md`.
