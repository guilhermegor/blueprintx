<!-- readme-archetype: ${README_ARCHETYPE} -->
# ${PROJECT_DISPLAY_NAME}

<p align="center"><img src="https://raw.githubusercontent.com/${GITHUB_USERNAME}/${PROJECT_NAME}/main/assets/logo_lorem_ipsum.png" width="200" alt="${PROJECT_DISPLAY_NAME} logo"></p>

[![Project Status: Active](https://www.repostatus.org/badges/latest/active.svg)](https://www.repostatus.org/#active)
![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)
<!-- only: library -->
[![PyPI](https://img.shields.io/pypi/v/${PROJECT_NAME}.svg)](https://pypi.org/project/${PROJECT_NAME}/)
<!-- /only -->
[![Docs](https://img.shields.io/badge/docs-latest-blue.svg)](https://${GITHUB_USERNAME}.github.io/${PROJECT_NAME}/)
[![Linting](https://img.shields.io/badge/linting-ruff_|_codespell-blue)](https://github.com/astral-sh/ruff)
[![Mypy](https://img.shields.io/badge/type_checked-mypy-blue)](https://mypy-lang.org)
![Test Coverage](https://raw.githubusercontent.com/${GITHUB_USERNAME}/${PROJECT_NAME}/main/coverage.svg)
![License](https://img.shields.io/badge/license-${PROJECT_LICENSE}-green.svg)
![Open Issues](https://img.shields.io/github/issues/${GITHUB_USERNAME}/${PROJECT_NAME})
![Contributions Welcome](https://img.shields.io/badge/contributions-welcome-darkgreen.svg)

<!-- slug: overview -->
## Overview

${PROJECT_DESCRIPTION}

<!-- optional section: delete it when the project has no feature list -->
<!-- slug: features -->
## Features

- The capabilities users care about, one line each.

<!-- only: library -->
<!-- slug: documentation -->
## Documentation

The documentation site lives at https://${GITHUB_USERNAME}.github.io/${PROJECT_NAME}/. Serve it locally with `bash bin/poe_exec.sh docs_serve`.
<!-- /only -->

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

After the bootstrap under Install, every task runs through the same entry point:
`bash bin/poe_exec.sh <task>`, and `bash bin/poe_exec.sh` with no task lists them.

```bash
poetry run pytest tests/unit/ -v
poetry run pytest tests/integration/ -v
```

<!-- only: library -->
Once the first release's docs deploy has created the `gh-pages` branch, run
`bash bin/poe_exec.sh enable_pages` once: until that branch exists, `init` leaves Pages untouched.
<!-- /only -->

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
<!-- only: library -->
- [Documentation](https://${GITHUB_USERNAME}.github.io/${PROJECT_NAME}/)
<!-- /only -->

---

<sub>Generated from the ${README_TIER} template via BlueprintX.</sub>
<!-- add any project disclaimer inside the sub tag above; for a library wrapping a third party, e.g. "Unofficial, community library. Not affiliated with or endorsed by <Org>." -->
