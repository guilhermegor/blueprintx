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
  .github/workflows/tests.yaml
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

The generated `tests/unit/test_main.py` asserts that this output appears using `unittest`:

```python
# tests/unit/test_main.py
import io
import sys
import unittest
from <project_name>.main import main

class TestMain(unittest.TestCase):
    def test_main_prints_hello(self) -> None:
        cls_buffer = io.StringIO()
        sys.stdout = cls_buffer
        main()
        sys.stdout = sys.__stdout__
        self.assertIn("Hello", cls_buffer.getvalue())
```

---

## 🛠️ Tooling (inherited from `python-common`)

| Tool | Role | Config file |
|------|------|------------|
| **Ruff** | Linter + formatter | `ruff.toml` — line-length 99, tab indent, double quotes, NumPy docstrings |
| **pre-commit** | Git hooks | `.pre-commit-config.yaml` — ruff, pydocstyle, codespell, commitizen, gitlint, unit + integration tests, coverage badge |
| **unittest** | Test runner | Discovered with `python -m unittest discover -s tests/unit -p "*.py"` |
| **pytest** | Alternative runner | `pytest.ini` included for compatibility; `poetry run pytest` also works |
| **GitHub Actions** | CI | `.github/workflows/tests.yaml` — runs linting and tests on every push |
| **Makefile + `bin/`** | Dev automation | `make init_venv`, `make update_venv`, `make start`, linting and test recipes |

---

## 🔄 Typical workflow

1. Add library functions and classes under `src/<project_name>/`.
2. Mirror the source structure under `tests/unit/` — one test module per source module.
3. Run tests: `python -m unittest discover -s tests/unit -p "*.py" -v`
4. Add integration tests in `tests/integration/` for any I/O-dependent code.
5. Keep `docs/` in sync with the public API; host locally with `make docs_server`.

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
import unittest
from <project_name>.math_utils import add

class TestMathUtils(unittest.TestCase):
    def test_add_two_positive_ints_returns_sum(self) -> None:
        self.assertEqual(add(2, 3), 5)

    def test_add_negative_int_returns_correct_sum(self) -> None:
        self.assertEqual(add(-1, 1), 0)
```
