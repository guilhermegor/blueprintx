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
the project: two other code files import it. Remove these three together:

| # | File | What to remove |
|---|------|----------------|
| 1 | `src/<package_name>/main.py` | Delete the file |
| 2 | `tests/unit/test_main.py` | Delete the file (it imports `main`) |
| 3 | `src/<package_name>/__init__.py` | Delete `from .main import main` and the `"main"` entry in `__all__` (`"__version__"` stays); without this, `import <package_name>` fails |

Docs still show `main` afterwards, in English and in `docs/pt-BR/`. They do not
break the build (the "Module: `main`" section is a plain code block, not a
mkdocstrings `:::` directive), but they document a function that no longer
exists:

| # | File | What to change |
|---|------|----------------|
| 4 | `docs/usage.md` and `docs/pt-BR/usage.md` | Replace the "Basic usage" example (`from <package_name>.main import main`) with one of your own public functions |
| 5 | `docs/examples.md` and `docs/pt-BR/examples.md` | Replace the first recipe, which imports `main` from the package |
| 6 | `docs/api/reference.md` and `docs/pt-BR/api/reference.md` | In the English page delete the "Module: `main`" section and this section; in the pt-BR page delete only "Módulo: `main`" (it has no removal section). In both, delete the `---` rules between the removed sections too, leaving exactly one `---` between the preceding section and "Adding new modules" |
| 7 | `AGENTS.md` | Update the layout tree and the "example boilerplate" note that name `main.py` |

No other code file references `main`: `pyproject.toml` has no `[project.scripts]`
entry, and neither `poe_tasks.toml` nor `.coveragerc` names it.

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
