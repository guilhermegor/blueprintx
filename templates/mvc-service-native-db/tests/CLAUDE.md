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

`pytest.ini` sets `pythonpath = .` (project root), so import the code under test through the
`src` package:

```python
from src.view.report_renderer import RenderToExcel
from src.model.example_entity import ExampleEntity
```

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
