<!-- readme-archetype: ${README_ARCHETYPE} -->
# ${PROJECT_DISPLAY_NAME}

<p align="center"><img src="assets/logo_lorem_ipsum.png" width="200" alt="${PROJECT_DISPLAY_NAME} logo"></p>

[![Project Status: Active](https://www.repostatus.org/badges/latest/active.svg)](https://www.repostatus.org/#active)
![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)
[![Linting](https://img.shields.io/badge/linting-ruff_|_codespell-blue)](https://github.com/astral-sh/ruff+https://github.com/codespell-project/codespell)
![Formatting: isort](https://img.shields.io/badge/formatting-isort-%231674b1)
![Test Coverage](./coverage.svg)
![License](https://img.shields.io/badge/license-${PROJECT_LICENSE}-green.svg)
![Open Issues](https://img.shields.io/github/issues/${GITHUB_USERNAME}/${PROJECT_NAME})
![Contributions Welcome](https://img.shields.io/badge/contributions-welcome-darkgreen.svg)

<!-- slug: overview -->
## Overview

${PROJECT_DESCRIPTION}

<!-- slug: getting-started -->
## Getting Started

Python 3.10+ is the only prerequisite; `bin/venv.sh` installs [Poetry](https://python-poetry.org/) when it is missing.

<!-- slug: install -->
### Install

```bash
git clone https://github.com/${GITHUB_USERNAME}/${PROJECT_NAME}.git
cd ${PROJECT_NAME}
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
${PROJECT_NAME}/
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

```bash
poetry run pytest tests/unit/ -v
poetry run pytest tests/integration/ -v
```

<!-- only: service -->
<!-- slug: configuration -->
## Configuration

Runtime settings live in `.env` (copy it from `.env.example`) and under `src/config/`.
<!-- /only -->
<!-- only: library -->
<!-- slug: public-api -->
## Public API

The public surface is whatever the package `__init__.py` lists in `__all__`; everything
under `_internal/` is private.

<!-- slug: publishing -->
## Publishing

Releases go out from the release workflows under `.github/workflows/`; the git tag is the
version.
<!-- /only -->

<!-- slug: contributing -->
## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for the branch, commit and review rules.

<!-- slug: license -->
## License

This project is licensed under ${PROJECT_LICENSE}; see [LICENSE](LICENSE).

<!-- slug: authors -->
## Authors

- ${AUTHOR_NAME} — [GitHub](https://github.com/${GITHUB_USERNAME}) | [LinkedIn](${LINKEDIN_URL})

<!-- slug: useful-links -->
## Useful Links

- [GitHub Repository](https://github.com/${GITHUB_USERNAME}/${PROJECT_NAME})
- [Issue Tracker](https://github.com/${GITHUB_USERNAME}/${PROJECT_NAME}/issues)
