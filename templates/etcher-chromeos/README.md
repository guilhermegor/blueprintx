<!-- readme-archetype: usb-tool -->
# ${PROJECT_NAME}

<!-- slug: overview -->
## Overview

${PROJECT_DESCRIPTION}

Rebuilds a ChromeOS-family pendrive: pick the target device, pick **ChromeOS Flex** or
**FydeOS**, and the CLI fetches (Flex) or verifies (FydeOS) the image and writes it.
The image defines the partition layout; this tool selects, verifies and flashes.

<!-- slug: getting-started -->
## Getting Started

<!-- slug: install -->
### Install

```bash
make tools   # uses the distro bmaptool, else tells you how to install it
```

<!-- slug: usage -->
### Usage

```bash
bin/${PROJECT_NAME} flash                   # asks for the pendrive path first
bin/${PROJECT_NAME} flash --target /dev/sdb --os chromeos-flex --dry-run
bin/${PROJECT_NAME} flash --target /dev/sdb --os fydeos \
    --file ~/Downloads/FydeOS_for_PC_v19.0-io-stable.img.xz --sha256 <published-hash>
```

- **Target.** The first step. The path is resolved to the whole disk; a device that is not
  removable, or has mounted partitions, is refused.
- **ChromeOS Flex.** The latest image is resolved from Google's recovery manifest
  (`cloudready_recovery2.json`, channel `STABLE` unless `--channel`). The zip size, the
  image size and the SHA-1 it publishes are all checked before anything is written. The
  image is about 9.5 GB, so use a 16 GB or larger pendrive.
- **FydeOS.** The download page publishes a SHA-256 per variant but no scriptable,
  unauthenticated "latest" URL, so you download the file and pass its published hash.
  The hash is checked against the archive before it is unpacked.
- **Flashing.** The distro's `bmaptool` when installed (`apt install bmap-tools`), else
  `dd conv=fsync status=progress`, which needs no download. `make tools` only checks for
  bmaptool and never downloads it. balenaEtcher has no maintained CLI;
  `make tools_etcher ALLOW_UNSIGNED_DOWNLOAD=1` fetches the GUI, verified only against a
  digest served by the same release, not publisher-attested. Every flash shows the
  device's model, size and partitions and requires typing the device name. `--dry-run`
  writes nothing.
- **Docker.** The `Dockerfile` is for tests and resolvers only. It cannot flash: that would
  need `--privileged` and would lose the removable-device check.

<!-- slug: project-structure -->
## Project Structure

```text
${PROJECT_NAME}/
├── bin/${PROJECT_NAME}   CLI entrypoint
├── lib/                  device, image and flashing helpers
├── tests/                bats suites (network and devices stubbed)
├── Dockerfile            tests and resolvers only
└── .specs/               feature specs and backlog trackers
```

Feature specs live under `.specs/features/`; `.specs/CLAUDE.md` holds the layout rules.

<!-- slug: development -->
## Development

```bash
make lint     # shellcheck + shfmt
make test     # bats tests/ (network and devices stubbed)
```

<!-- slug: payload -->
## Payload

The default for `--os` is stamped at scaffold time (`DEFAULT_OS` in `bin/${PROJECT_NAME}`).

<!-- slug: releasing -->
## Releasing

The version is the git tag; there is no hand-bump. Cut a release from the **Release**
GitHub Action (`.github/workflows/release.yml`, `workflow_dispatch` with a `version`).

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
