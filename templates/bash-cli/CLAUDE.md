# CLAUDE.md

Guidance for Claude Code when working in this repository — a standalone Bash CLI
scaffolded from BlueprintX's `bash-cli` skeleton.

## Engineering principles

See @PRINCIPLES.md for the single-responsibility and function-design rules this project follows.

## Layout

- `bin/${PROJECT_NAME}` — the entrypoint. `CLI_VERSION="0.0.0"` is a stub; `make
  install` / the Release workflow stamp the real value from the git tag. A git
  checkout always resolves the version from `git describe --tags` instead.
- `lib/common.sh` — shared `print_status` (colour, level-routed output). Sourced by
  the entrypoint; source it from any new script the same way.
- `tests/*.bats` — bats tests. `make test` runs them.

## Conventions

- Every script sources `lib/common.sh` and uses `print_status`, never a bare
  `echo`/`printf` for status output (plain data the caller parses is not status).
- `make lint` (shellcheck + shfmt) and `make test` (bats) are the same commands CI
  runs — no separate CI-only logic.
- New commands: extend the `case` in `bin/${PROJECT_NAME}`'s `main()`, add a bats
  test for it in `tests/`.

## Releasing

The version is the git tag — there is no hand-bump. See README.md → "Releasing".
