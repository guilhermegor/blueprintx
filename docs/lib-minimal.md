# **Lib Minimal (library starter)**

A lean Python library skeleton with packaging, testing, CI, and editor settings ready to go.

## Expected layout (after scaffold)
```
project/
  src/<project_name>/
    __init__.py
    main.py
  tests/
    unit/test_main.py
    integration/
    performance/
  assets/
  data/
  docs/
  container/
  scripts/
  .github/workflows/tests.yaml
  .vscode/settings.json
  .env
  pyproject.toml
  README.md
```
Shared Python assets (pyproject, pre-commit, README boilerplate, VS Code, CI) come from `templates/python-common`.

## Folder Descriptions

| Folder | Purpose | Expected Content |
|--------|---------|------------------|
| `src/<project_name>/` | Library source code | Python modules, classes, functions — your library's public API |
| `tests/unit/` | Unit tests | Fast, isolated tests for individual functions and classes |
| `tests/integration/` | Integration tests | Tests with external dependencies (databases, APIs, file systems) |
| `tests/performance/` | Performance tests | Benchmarks, load tests, memory profiling |
| `assets/` | Static resources | Images, icons, fonts, static files bundled with the library |
| `data/` | Data storage | SQLite databases, CSV files, XLSX files, JSON data, fixtures, seed data |
| `docs/` | Documentation | API reference, tutorials, user guides (starter `index.md` created) |
| `container/` | Container configuration | Dockerfile, docker-compose.yaml for containerized environments |
| `scripts/` | Utility scripts | Build scripts, automation, CLI helpers |
| `.github/workflows/` | CI/CD pipelines | GitHub Actions for tests, linting, publishing to PyPI |
| `.vscode/` | Editor settings | VS Code workspace settings, recommended extensions, debug configs |

## Starting points
Sample entrypoint: [templates/lib-minimal/main.py](https://github.com/guilhermegor/BlueprintX/blob/main/templates/lib-minimal/main.py#L1-L2)
```python
def main():
    print("Hello from lib-minimal!")
```
The generated `tests/unit/test_main.py` asserts that this output appears.

## Typical workflow
1. Add library functions/classes under `src/<project_name>/`.
2. Add or expand tests in `tests/unit/` (and integration/performance as needed).
3. Run tests with Poetry: `poetry run pytest`.
4. Keep the docs (`docs/`) in sync with assets APIs; you can host them with mkdocs like the BlueprintX docs.

## Example feature addition
```python
# src/<project_name>/math_utils.py
def add(a: int, b: int) -> int:
    return a + b
```
```python
# tests/unit/test_math_utils.py
from <project_name>.math_utils import add

def test_add():
    assert add(2, 3) == 5
```
