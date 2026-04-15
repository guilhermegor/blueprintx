# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this template is

A **minimal Python library / CLI starter**. No DDD structure, no database wiring — just a clean package layout with CI, pre-commit, and test folders ready to go. It is scaffolded by BlueprintX into a new project directory.

The scaffold script replaces `<project_name>` directory names and the `pyproject.toml` placeholders via `envsubst`.

## Layout

```
src/<project_name>/
    __init__.py
    main.py          # single entry-point; rename or split as the lib grows
tests/
    unit/
    integration/
    performance/
```

`main.py` currently contains only a bare `main()` function — the intended starting point for the library's public API or CLI entry point.

## Conventions (inherited from `templates/python-common/`)

- **One public class per file.** Module-level functions are preferred over utility classes when there is no shared state.
- **Ruff**: linter + formatter. Line-length 99, tab indent, double quotes, NumPy docstrings (`ruff.toml`).
- **Pre-commit**: ruff, pydocstyle, codespell, commitizen, gitlint, unit + integration tests, coverage badge.
- **Tests**: `unittest` — `python -m unittest discover -s tests/unit -p "*.py"`.
- **Makefile**: `init-venv`, `update-venv`, `vscode_init`, `export_deps`.

## Extending this template

This skeleton intentionally has no opinions beyond tooling. When adding features:
- Keep `src/<project_name>/` as the importable package root.
- Add sub-packages as the project grows — do not dump everything into `main.py`.
- Mirror the test folder hierarchy to match `src/` structure.
