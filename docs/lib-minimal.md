# Lib Minimal (library starter)

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
  docs/
  container/
  bin/
  .github/workflows/tests.yaml
  .vscode/settings.json
  .env
  pyproject.toml
  README.md
```
Shared Python assets (pyproject, pre-commit, README boilerplate, VS Code, CI) come from `templates/python-common`.

## Purpose of each folder
- `src/<project_name>`: your library code. The scaffold seeds `main.py` with a tiny entrypoint.
- `tests/unit`: fast tests; scaffold adds a sample `test_main.py` that invokes the entrypoint.
- `tests/integration` and `tests/performance`: reserved for slower suites.
- `docs`: place project documentation (a starter `docs/index.md` is created).
- `container` and `bin`: optional CLI and container tooling.
- `.github/workflows`: CI pipeline (pytest + lint hooks once you add tools).
- `.vscode`: sensible editor defaults for Python projects.

## Starting points
Sample entrypoint: [templates/lib-minimal/main.py](templates/lib-minimal/main.py#L1-L2)
```python
def main():
    print("Hello from lib-minimal!")
```
The generated `tests/unit/test_main.py` asserts that this output appears.

## Typical workflow
1. Add library functions/classes under `src/<project_name>/`.
2. Add or expand tests in `tests/unit/` (and integration/performance as needed).
3. Run tests with Poetry: `poetry run pytest`.
4. Keep the docs (`docs/`) in sync with public APIs; you can host them with mkdocs like the blueprintx docs.

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
