<!-- readme-archetype: ${README_ARCHETYPE} -->
# ${PROJECT_DISPLAY_NAME}

<p align="center"><img src="https://raw.githubusercontent.com/${GITHUB_USERNAME}/${PROJECT_NAME}/main/assets/logo_lorem_ipsum.png" width="200" alt="${PROJECT_DISPLAY_NAME} logo"></p>

[![Project Status: Active](https://www.repostatus.org/badges/latest/active.svg)](https://www.repostatus.org/#active)
![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)
<!-- only: library -->
[![PyPI](https://img.shields.io/pypi/v/${PROJECT_NAME}.svg)](https://pypi.org/project/${PROJECT_NAME}/)
[![Downloads](https://img.shields.io/pepy/dt/${PROJECT_NAME})](https://pepy.tech/projects/${PROJECT_NAME})
<!-- /only -->
[![Docs](https://img.shields.io/badge/docs-latest-blue.svg)](https://${GITHUB_USERNAME}.github.io/${PROJECT_NAME}/)
[![Linting](https://img.shields.io/badge/linting-ruff_%7C_codespell-blue)](https://github.com/astral-sh/ruff)
[![Mypy](https://img.shields.io/badge/type--checked-mypy-blue)](https://mypy-lang.org)
![Test Coverage](https://raw.githubusercontent.com/${GITHUB_USERNAME}/${PROJECT_NAME}/badges/coverage.svg)
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

The documentation site lives at https://${GITHUB_USERNAME}.github.io/${PROJECT_NAME}/. Serve it locally with `poetry run poe docs_serve`.
<!-- /only -->

<!-- slug: getting-started -->
## Getting Started

Python 3.11+ is the only prerequisite; `bin/venv.sh` installs [Poetry](https://python-poetry.org/) when it is missing.

<!-- slug: install -->
### Install

```bash
git clone https://github.com/${GITHUB_USERNAME}/${PROJECT_NAME}.git
cd ${PROJECT_NAME}
bash bin/venv.sh
poetry run poe init
```

`poe` lives inside the virtualenv, so `bin/venv.sh` creates it first; `poetry run poe init` then
runs it without activating anything. If `poetry` is not on `PATH` (for example right after
`bin/venv.sh` installed it with `--user`), use `bash bin/poe_exec.sh init`, which finds the
venv's `poe` on its own. Behind a TLS-inspecting proxy with `bin/corporate_ca.pem` in place, run
`init` through `bash bin/poe_exec.sh init` so the CA bundle is wired for the downloads.

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

After the bootstrap under Install, any task can be run with
`poetry run poe <task>`, and `poetry run poe` with no task lists them.

```bash
poetry run poe unit_tests
poetry run poe integration_tests
```

<!-- only: library -->
Once the first release's docs deploy has created the `gh-pages` branch, run
`poetry run poe enable_pages` once: until that branch exists, `init` leaves Pages untouched.
<!-- /only -->

### `poetry run poe` or `bash bin/poe_exec.sh`?

Both run the same task through the same venv `poe`. Use `poetry run poe`, the command the
community knows best; `bin/poe_exec.sh` covers the cases where it is not enough:

| Case | `poetry run poe` | `bash bin/poe_exec.sh` |
|---|---|---|
| Normal machine, `poetry` on `PATH` | works | works |
| `poetry` not on `PATH` (e.g. right after `bin/venv.sh` installed it with `--user`) | fails: `poetry: command not found` | works: finds `.venv/bin/poe` (`.venv/Scripts/poe.exe` on Windows) without `poetry` |
| Corporate TLS-inspecting network, with `bin/corporate_ca.pem` present | gets no CA bundle; tasks that download can fail TLS | works: builds a union CA bundle and exports `REQUESTS_CA_BUNDLE`, `SSL_CERT_FILE`, `CURL_CA_BUNDLE` and `PIP_CERT` before the task runs |
| `poe` not installed | generic Poetry error | prints the install routes (`bin/venv.sh`, `pipx`, Poetry plugin) |

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

The path from 0.x to 1.0.0, and the release gate that guards it, is in
[docs/releasing-1-0-0.md](docs/releasing-1-0-0.md).
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

<sub>Generated from the ${README_TIER} template via [BlueprintX](https://github.com/guilhermegor/blueprintx).</sub>
<!-- add any project disclaimer inside the sub tag above; for a library wrapping a third party, e.g. "Unofficial, community library. Not affiliated with or endorsed by ORG_NAME." -->
