# AGENTS.md

Guidance for agents working in this repository: a Bash CLI that flashes ChromeOS Flex
or FydeOS to a USB pendrive, scaffolded from BlueprintX's `etcher-chromeos` skeleton.

## Engineering principles

Read `PRINCIPLES.md` for the single-responsibility and function-design rules this project follows.

## Layout

- `bin/${PROJECT_NAME}` is the entrypoint (`flash` command). `CLI_VERSION="0.0.0"` is a
  stub; `make install` and the Release workflow stamp the real value from the git tag.
- `lib/device.sh` resolves the target and refuses a non-removable or mounted device.
- `lib/flex.sh` resolves the latest image from Google's recovery manifest and verifies it.
- `lib/fydeos.sh` verifies a FydeOS image you downloaded (no scriptable download exists).
- `lib/flash.sh` builds the `bmaptool`/`dd` command; `lib/verify.sh` holds the checks.
- `bin/fetch_tools.sh` fills the git-ignored `.tools/` cache (`make tools`).
- `tests/*.bats` stub the network and every device tool. Never point a test at a real
  device, and never run `flash` against one without `--dry-run` unless asked to.

## Conventions

- Every script sources `lib/common.sh` and uses `print_status`.
- `make lint` and `make test` are the same commands CI runs.
- Images (`*.bin *.img *.zip *.xz`) and `.tools/` are never committed.

## Releasing

The version is the git tag; there is no hand-bump. See README.md.
