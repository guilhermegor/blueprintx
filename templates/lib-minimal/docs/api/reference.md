# **API Reference**

Public interface for this library.

> **See also:** [Usage](../usage.md)

---

## Module: `main`

Entry point module. Extend this with your library's public functions.

### `main() -> None`

Runs the library entry point. Replace the body with your top-level logic.

```python
from <package_name>.main import main

main()
```

---

## Removing the starter `main`

`main` is a placeholder. Deleting `src/<package_name>/main.py` on its own breaks
the project, because three other places still reference it. Remove all four
together:

| # | File | What to remove |
|---|------|----------------|
| 1 | `src/<package_name>/main.py` | Delete the file |
| 2 | `tests/unit/test_main.py` | Delete the file (it imports `main`) |
| 3 | `src/<package_name>/__init__.py` | Delete `from .main import main` and the `"main"` entry in `__all__`; without this, `import <package_name>` fails |
| 4 | `docs/api/reference.md` | Delete the `## Module: main` section above |

`docs/usage.md` also shows `from <package_name>.main import main` under
"Basic usage"; replace that example with one of your own public functions.
No `[project.scripts]` entry points at `main`, so `pyproject.toml` needs no
change.

---

## Adding new modules

Place new modules under `src/<package_name>/`. Export public symbols from `src/<package_name>/__init__.py` so callers can do:

```python
from <package_name> import my_function
```

Follow the one-class-per-file convention: utility functions with no shared state belong at module level, not wrapped in a class.

---

## Conventions

| Convention | Rule |
|------------|------|
| Type hints | Required on all public functions, including `-> None` return types |
| Docstrings | NumPy style; explain *why*, not *what* |
| Variable names | Type-prefixed (`str_`, `list_`, `cls_`, `dict_`, …) |
| Testing | `unittest`; one assertion per test; name as `test_<unit>_<scenario>_<expected>` |
