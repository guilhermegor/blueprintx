<!-- readme-archetype: library -->
# docs-probe

<p align="center"><img src="https://raw.githubusercontent.com/ci-bot/docs-probe/main/assets/logo_lorem_ipsum.png" width="200" alt="docs-probe logo"></p>

[![Project Status: Active](https://www.repostatus.org/badges/latest/active.svg)](https://www.repostatus.org/#active)
![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)
[![PyPI](https://img.shields.io/pypi/v/docs-probe.svg)](https://pypi.org/project/docs-probe/)
[![Downloads](https://img.shields.io/pepy/dt/docs-probe)](https://pepy.tech/projects/docs-probe)
[![Docs](https://img.shields.io/badge/docs-latest-blue.svg)](https://ci-bot.github.io/docs-probe/)
[![Linting](https://img.shields.io/badge/linting-ruff_%7C_codespell-blue)](https://github.com/astral-sh/ruff)
[![Mypy](https://img.shields.io/badge/type--checked-mypy-blue)](https://mypy-lang.org)
![Test Coverage](https://raw.githubusercontent.com/ci-bot/docs-probe/badges/coverage.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Open Issues](https://img.shields.io/github/issues/ci-bot/docs-probe)
![Contributions Welcome](https://img.shields.io/badge/contributions-welcome-darkgreen.svg)

<!-- slug: overview -->
## Overview

Docs probe

<!-- optional section: delete it when the project has no feature list -->
<!-- slug: features -->
## Features

- The capabilities users care about, one line each.

<!-- slug: documentation -->
## Documentation

The documentation site lives at https://ci-bot.github.io/docs-probe/. Serve it locally with `bash bin/poe_exec.sh docs_serve`.

<!-- slug: getting-started -->
## Getting Started

Python 3.11+ is the only prerequisite; `bin/venv.sh` installs [Poetry](https://python-poetry.org/) when it is missing.

<!-- slug: install -->
### Install

```bash
git clone https://github.com/ci-bot/docs-probe.git
cd docs-probe
bash bin/venv.sh
bash bin/poe_exec.sh init
```

`poe` lives inside the virtualenv, so `bin/venv.sh` creates it first; `bin/poe_exec.sh` then
runs `poe init` without activating anything.

<!-- slug: usage -->
### Usage

Run the project through its entry points under `src/`; replace this paragraph with the
commands your users run first.

<!-- slug: project-structure -->
## Project Structure

```text
docs-probe/
├── .github/        workflows, CODEOWNERS, PR template
├── .specs/         feature specs and backlog trackers
├── bin/            gate scripts and helpers
├── docs/           published documentation
├── src/            application code
├── tests/
│   ├── unit/
│   └── integration/
├── pyproject.toml
└── poe_tasks.toml  task runner entry points
```

<!-- slug: development -->
## Development

After the bootstrap under Install, any task can be run with the bootstrap script:
`bash bin/poe_exec.sh <task>`, and `bash bin/poe_exec.sh` with no task lists them.

```bash
bash bin/poe_exec.sh unit_tests
bash bin/poe_exec.sh integration_tests
```

Once the first release's docs deploy has created the `gh-pages` branch, run
`bash bin/poe_exec.sh enable_pages` once: until that branch exists, `init` leaves Pages untouched.

<!-- slug: public-api -->
## Public API

The public surface is whatever the package `__init__.py` lists in `__all__`; everything
under `_internal/` is private.

<!-- slug: publishing -->
## Publishing

Releases go out from the release workflows under `.github/workflows/`; the git tag is the
version.

The path from 0.x to 1.0.0, and the release gate that guards it, is in
[docs/releasing-1-0-0.md](docs/releasing-1-0-0.md).

<!-- slug: contributing -->
## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the branch, commit and review rules.

<!-- slug: license -->
## License

This project is licensed under MIT; see [LICENSE](LICENSE).

<!-- slug: authors -->
## Authors

- ci-bot — [GitHub](https://github.com/ci-bot) | [LinkedIn](https://www.linkedin.com/in/ci-bot)

<!-- slug: useful-links -->
## Useful Links

- [GitHub Repository](https://github.com/ci-bot/docs-probe)
- [Issue Tracker](https://github.com/ci-bot/docs-probe/issues)
- [Documentation](https://ci-bot.github.io/docs-probe/)

---

<sub>Generated from the lib-minimal template via [BlueprintX](https://github.com/guilhermegor/blueprintx).</sub>
<!-- add any project disclaimer inside the sub tag above; for a library wrapping a third party, e.g. "Unofficial, community library. Not affiliated with or endorsed by ORG_NAME." -->
