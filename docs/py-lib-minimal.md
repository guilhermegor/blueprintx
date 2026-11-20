# **Lib Minimal (library starter)**

A lean Python library skeleton with packaging, testing, CI, and editor settings ready to go. No DDD structure, no database wiring — just a clean package layout so you can focus on writing library code from the first commit.

Shared tooling (Ruff, pre-commit, pytest.ini, GitHub Actions CI, Makefile, `bin/` helpers, VS Code config) comes from `templates/python-common` and is copied verbatim at scaffold time.

---

## 🗂️ Expected layout (after scaffold)

```bash
project/
  src/<project_name>/
    __init__.py
    main.py               # single entry-point; rename or split as the lib grows
  tests/
    unit/test_main.py
    integration/
    performance/
  bin/                    # shell helpers called by the Makefile
  container/
  assets/
  data/
  docs/
  .github/workflows/tests.yml
  .env
  pyproject.toml
  README.md
  ruff.toml
  pytest.ini
  .pre-commit-config.yaml
```

---

## 📁 Folder Descriptions

| Folder | Purpose | Expected Content |
|--------|---------|------------------|
| `src/<project_name>/` | Library source code | Python modules, classes, functions — your library's public API |
| `src/<project_name>/_internal/utils/` | Vendored utilities | Private copies of the shared helpers, including `dates.py` (Brazilian business days via `purecalendars`) and `zip_extractor.py`; every Python tier ships both |
| `tests/unit/` | Unit tests | Fast, isolated tests for individual functions and classes |
| `tests/integration/` | Integration tests | Tests with external dependencies (databases, APIs, file systems) |
| `tests/performance/` | Performance tests | Benchmarks, load tests, memory profiling |
| `bin/` | Shell helpers | Entry-point scripts called by the `Makefile`; keeps recipes thin |
| `assets/` | Static resources | Images, icons, fonts, static files bundled with the library |
| `data/` | Data storage | SQLite databases, CSV files, JSON fixtures, seed data |
| `docs/` | Documentation | API reference, tutorials, user guides (starter `index.md` created) |
| `container/` | Container configuration | Dockerfile, docker-compose.yaml for containerised environments |
| `.github/workflows/` | CI/CD pipelines | GitHub Actions for tests, linting, publishing to PyPI |

---

## 🚀 Starting point

The generated `main.py` contains one bare function — the intended starting point for the library's public API or CLI entry point:

```python
# src/<project_name>/main.py
def main() -> None:
    print("Hello from lib-minimal!")
```

The generated `tests/unit/test_main.py` asserts that this output appears using `pytest`:

```python
# tests/unit/test_main.py
"""Unit tests for the library entry point."""

import pytest

from <project_name>.main import main


def test_main(capsys: pytest.CaptureFixture[str]) -> None:
    """The entry point prints the placeholder greeting to stdout."""
    main()
    captured = capsys.readouterr()
    assert "Hello from lib-minimal!" in captured.out
```

---

## 🪶 Zero-dependency mode

The scaffold asks "Zero runtime dependencies?" (spec key `zero_dependency`, default `n`). The default ships the full vendored `_internal` toolkit, `dates.py` included, backed by beartype, pandas, numpy, purecalendars, openpyxl and defusedxml.

Answering `y` leaves the whole toolkit out as one group (dtypes, tabular and XML readers, `dates.py`, downloaders, regime modules, `_internal/config/contracts` and `_internal/config/ports`) together with its tests. It ships a stdlib-only `type_checker` in `_internal/utils/typing/` instead of the beartype-backed one, and the generated `pyproject.toml` has an empty `[tool.poetry.dependencies]` apart from `python`. Dev tooling is unchanged.

The stdlib `type_checker` validates arguments annotated with a plain class (`str`, `int`) and leaves generic, union and string annotations to mypy. A stdlib `TypeChecker` metaclass (`_internal/utils/typing/type_checker_meta.py`) applies `type_checker` to every public, not-yet-wrapped method of a class, plus `__init__` (other dunders are left alone). `check_typing.py` requires every root class under `src/` to declare `metaclass=TypeChecker` (or `ABCTypeCheckerMeta` / `ProtocolTypeCheckerMeta`), so a class in a zero-dependency project writes `class Foo(metaclass=TypeChecker)`; the ABC and Protocol variants need the vendored toolkit and are not shipped here. The OTLP log export and the in-repo `logs.py` helper belong to the vendored toolkit, so each is skipped with a warning when chosen together with zero-dependency mode.

### Aligning an existing library

A library that adopts this scaffold file by file must re-decide `zero_dependency` for itself rather than copy the generic answer. The default ships the vendored toolkit and its runtime dependencies whether or not the library's public modules reach them (purecalendars #97: five required dependencies and the placeholder `main.py` were one release away from a pure offline calendar library).

Before the first release after the alignment, run `python3 bin/check_template_residue.py` in the project. It fails while any `src/<pkg>/main.py` still holds the template's greeting literal (`Hello from lib-minimal!`, matched as a string constant so reformatting does not hide it), and it lists the `_internal/utils` modules no public module reaches through imports (everything outside `_internal`, plus `__init__`), with the third-party imports only those modules make. Delete each listed module with its tests and the dependencies only it uses, or allowlist it in `.unreachable-modules.txt` with the reason it is loaded dynamically.

The report alone exits 0. `release-pypi.yaml` runs it with `--strict` in its `template_residue` job, before the build, so a release fails on any finding. It runs nowhere else: a fresh scaffold carries the placeholder and the unwired toolkit by design, and its tests, lint and pre-commit stay green until the first release asks the question.

---

## 🛠️ Tooling (inherited from `python-common`)

| Tool | Role | Config file |
|------|------|------------|
| **Ruff** | Linter + formatter | `ruff.toml` — line-length 99, 4-space indent, double quotes, NumPy docstrings |
| **pre-commit** | Git hooks | `.pre-commit-config.yaml` — ruff, pydocstyle, codespell, commitizen, gitlint, unit + integration tests, coverage badge |
| **pytest** | Test runner | `pytest.ini` — `poe unit_tests` runs `pytest tests/unit/`; tests are pytest-style functions with fixtures |
| **GitHub Actions** | CI | `.github/workflows/tests.yml` — runs linting and tests on every push |
| **`poe_tasks.toml` + `bin/`** | Dev automation | `poe venv`, `poe update_venv`, plus the linting and test tasks. Bare `poe` lists them all. Bootstrap is `bash bin/venv.sh` — poe is a dev dependency, so it lives inside the venv it would have to create |

---

## 🔄 Typical workflow

1. Add library functions and classes under `src/<project_name>/`.
2. Mirror the source structure under `tests/unit/` — one test module per source module.
3. Run tests: `poe unit_tests` (or `pytest tests/unit/ -v`)
4. Add integration tests in `tests/integration/` for any I/O-dependent code.
5. Keep `docs/` in sync with the public API; host locally with `poe docs_serve`.

---

## 💡 Example feature addition

```python
# src/<project_name>/math_utils.py
def add(int_a: int, int_b: int) -> int:
    """Return the sum of two integers."""
    return int_a + int_b
```

```python
# tests/unit/test_math_utils.py
from <project_name>.math_utils import add


def test_add_two_positive_ints_returns_sum() -> None:
    assert add(2, 3) == 5


def test_add_negative_int_returns_correct_sum() -> None:
    assert add(-1, 1) == 0
```
