# Bash CLI skeleton (`bash-cli`)

A standalone Bash CLI starter (`templates/bash-cli/`, `bin/scaffold/bash_cli.sh`).
This is the skeleton `publishprobe` (greenfield#26) is scaffolded from.

## What it ships

- `bin/<project-name>` — entrypoint with `--version`/`--help`, a `CLI_VERSION="0.0.0"`
  stub (stamped at install/release time, never hand-bumped).
- `lib/common.sh` — the same `print_status` implementation every BlueprintX
  skeleton ships (`templates/common/bin/lib/common.sh`), copied verbatim.
- `tests/cli.bats` — bats coverage for `--version`/`--help`/an unknown command.
- `Makefile` — `lint` (shellcheck + shfmt), `test` (bats), `install`.
- `.github/workflows/ci.yml` — lint + test jobs, each with `timeout-minutes`.
- `.github/workflows/release.yml`, `.pre-commit-config.yaml`, `.gitignore`,
  `README.md`, `CLAUDE.md`.

## Versioning — mirrors how BlueprintX releases itself

The version is the git tag, never a hand-bump:

- **From a git checkout** → `bin/<name>` runs `git describe --tags --always` at
  runtime, exactly like `bin/blueprintx.sh`'s own `print_version`.
- **From `make install`** (no `.git` at the install destination) → the recipe
  stamps the clone's current `git describe` into the installed entrypoint's
  `CLI_VERSION` literal via `sed`, mirroring the root `Makefile`'s `install` target.
- **From a Release** → `.github/workflows/release.yml` is BlueprintX's own
  `release.yml` orchestrator trimmed to the one channel v1 ships: a `tag` job
  (`workflow_dispatch` → `version` input, creates + pushes `vX.Y.Z`) followed by a
  `github_release` job that stamps that version into the tarball's entrypoint the
  same way, then publishes a GitHub Release with the tarball + a `.sha256` checksum.

## Deferred release channels (backlog)

BlueprintX itself also ships Homebrew, apt (gh-pages), Snap, and (optional)
Chocolatey sub-workflows (`.github/workflows/release_*.yml`) called from its
`release.yml` orchestrator. This skeleton's v1 ships only the GitHub Release +
`make install` leg — start small, verify the skeleton scaffolds/lints/tests green
first. Adding the remaining channels as `release_*.yml` sub-workflows (same
`workflow_call` + `needs: tag` pattern) is tracked in
`docs/backlog/bash-cli-skeleton_20260917_171817.md`.

## Verification

Dry-run coverage: `bash-cli` is in `dry-run-smoke`'s matrix
(`.github/workflows/scaffold_checks.yml`) — `bin/blueprintx.sh new --dry-run`
exercises the skeleton via `templates/*/skeleton.meta` discovery, no code change
needed there. A real scaffold + `make lint` + `make test` run is not yet wired
into `scaffold-lint-test` (that matrix is Python-only, driven by
`bin/ci/scaffold_lint_test.sh`, which is Poetry/pytest-specific and owned by a
sibling issue, #481) — verified manually for this PR instead (see PR description).
