# **Usage**

Examples for installing and using this library.

> **See also:** [API Reference](api/index.md)

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
poe run            # runs src/<package_name>/main.py
```

---

## Running tests

```bash
poe unit_tests         # unit tests only
poe integration_tests  # integration tests only
poe test_cov           # unit tests + coverage report + badge
```

---

## Linting and formatting

```bash
poe lint          # ruff check + ruff format + codespell + pydocstyle
```

---

## Publishing to PyPI

Two GitHub Actions workflows handle releases (present when the repo has a GitHub remote):

- **`release-test-pypi.yaml`** — publish to [Test PyPI](https://test.pypi.org) first.
- **`release-pypi.yaml`** — publish to [PyPI](https://pypi.org) and cut a GitHub release.

Trigger either from the **Actions** tab (`workflow_dispatch`) with the version to release.
Both gate on the new version being greater than the latest already published, build with
Poetry, and publish through OIDC trusted publishing, so no token secrets are needed.

Configure once, on each index (pypi.org and test.pypi.org), a pending publisher:

- PyPI: workflow `release-pypi.yaml`, environment `release-pypi`.
- Test PyPI: workflow `release-test-pypi.yaml`, environment `release-test-pypi`.

After the first `release-pypi.yaml` run creates the `gh-pages` branch, run `poe enable_pages`
once to serve the docs.
