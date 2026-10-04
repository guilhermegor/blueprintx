# ${PROJECT_NAME}

${PROJECT_DESCRIPTION}

## Usage

```bash
bin/${PROJECT_NAME} --help
bin/${PROJECT_NAME} --version
```

## Feature specs

Feature specs live under `.specs/features/` — copy `.specs/spec.md` for the
template and its `US-`/`AC-`/`ASM-`/`Q-XXX` id conventions.

## Development

```bash
make lint     # shellcheck + shfmt
make test     # bats tests/
```

## Install

```bash
make install  # stamps the current git-tag version into /usr/local/bin/${PROJECT_NAME}
```

## Releasing

The version is the git tag — there is no hand-bump. Cut a release from the
**Release** GitHub Action (`.github/workflows/release.yml`, `workflow_dispatch` →
`version` field): it tags `vX.Y.Z`, stamps that version into the packaged
entrypoint, and publishes a GitHub Release with the tarball + checksum.
