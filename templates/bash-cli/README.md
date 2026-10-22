<!-- readme-archetype: cli -->
# ${PROJECT_NAME}

<!-- slug: overview -->
## Overview

${PROJECT_DESCRIPTION}

<!-- slug: getting-started -->
## Getting Started

<!-- slug: install -->
### Install

```bash
make install  # stamps the current git-tag version into /usr/local/bin/${PROJECT_NAME}
```

<!-- slug: usage -->
### Usage

```bash
bin/${PROJECT_NAME} --help
bin/${PROJECT_NAME} --version
```

<!-- slug: project-structure -->
## Project Structure

```text
${PROJECT_NAME}/
├── bin/${PROJECT_NAME}   entrypoint
├── lib/                  shared helpers
├── tests/                bats suites
├── .specs/               feature specs and backlog trackers
└── Makefile              lint, test and install targets
```

Feature specs live under `.specs/features/`; `.specs/CLAUDE.md` holds the layout rules and
the template with its `US-`/`AC-`/`ASM-`/`Q-XXX` id conventions.

<!-- slug: development -->
## Development

```bash
make lint     # shellcheck + shfmt
make test     # bats tests/
```

<!-- slug: releasing -->
## Releasing

The version is the git tag — there is no hand-bump. Cut a release from the
**Release** GitHub Action (`.github/workflows/release.yml`, `workflow_dispatch` →
`version` field): it tags `vX.Y.Z`, stamps that version into the packaged
entrypoint, and publishes a GitHub Release with the tarball + checksum.

<!-- slug: contributing -->
## Contributing

Branch from `main`, use Conventional Commits, and open a pull request; the repository's
`.github/PULL_REQUEST_TEMPLATE.md` lists what a reviewer expects.

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
