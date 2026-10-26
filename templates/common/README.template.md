<!-- readme-archetype: ${README_ARCHETYPE} -->
# ${PROJECT_NAME}

<p align="center"><img src="https://raw.githubusercontent.com/${GITHUB_USERNAME}/${PROJECT_NAME}/main/assets/logo.png" width="200" alt="${PROJECT_DISPLAY_NAME} logo"></p>

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

<!-- slug: install -->
### Install

Prerequisites and the install command for pip and Poetry, extras included.

<!-- slug: usage -->
### Usage

The first command or call a user runs.

<!-- slug: project-structure -->
## Project Structure

```text
${PROJECT_NAME}/
├── src/
└── tests/
```

<!-- slug: development -->
## Development

How to run the tests and the linters.

<!-- only: library -->
<!-- slug: public-api -->
## Public API

What the package exports and what stays private.

<!-- slug: publishing -->
## Publishing

How a release reaches the package registry.
<!-- /only -->
<!-- only: cli -->
<!-- slug: releasing -->
## Releasing

How a tag becomes a published release.
<!-- /only -->
<!-- only: spa -->
<!-- slug: deployment -->
## Deployment

Where the built site is served from and how it gets there.
<!-- /only -->
<!-- only: service -->
<!-- slug: configuration -->
## Configuration

The environment variables and config files the service reads.
<!-- /only -->
<!-- only: usb-tool -->
<!-- slug: payload -->
## Payload

What is written to the device and where it comes from.
<!-- /only -->

<!-- slug: contributing -->
## Contributing

Branch, commit and review rules, or a link to `CONTRIBUTING.md`.

<!-- slug: license -->
## License

${PROJECT_LICENSE}; see [LICENSE](LICENSE).

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
<!-- add any project disclaimer inside the sub tag above -->
