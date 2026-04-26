# **Usage**

Examples for installing and using this library.

> **See also:** [API Reference](api.md)

---

## Installation

```bash
pip install <package-name>
```

Or with Poetry:

```bash
poetry add <package-name>
```

---

## Basic usage

```python
from <package_name>.main import main

main()
```

---

## Running from the Makefile

```bash
make start         # runs src/<package_name>/main.py via Poetry
```

---

## Running tests

```bash
make unit_tests         # unit tests only
make integration_tests  # integration tests only
make test_cov           # unit tests + coverage report + badge
```

---

## Linting and formatting

```bash
make lint          # ruff check + ruff format + codespell + pydocstyle
```
