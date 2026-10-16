# AGENTS.md

Guidance for agents working in this repository: a Ventoy drive builder scaffolded from
BlueprintX's `ventoy-usb` skeleton.

## Engineering principles

Read `PRINCIPLES.md` for the single-responsibility and function-design rules this project follows.

## Layout

- `sources.manifest`: the single source of truth. One line per payload; the drive tree and
  `ventoy/ventoy.json` are generated from it.
- `bin/${PROJECT_NAME}`: entrypoint (`layout`, `fetch`, `persistence`, `config`, `check`, `build`, `drive`).
- `lib/manifest.sh`, `resolve.sh`, `layout.sh`, `ventoy_config.sh`, `drive.sh`: one concern each;
  `lib/common.sh` is the shared `print_status`, copied verbatim.
- `ventoy-usb.conf`: the answers given at scaffold time (persistence size, optional groups).
- `tests/*.bats`: network is always stubbed (`CURL=tests/helpers/curl_stub.sh`).

## Conventions

- Payloads are never committed: `.gitignore` excludes `*.iso *.exe *.zip *.dat` and `build/`.
- Every download is checksum-verified or the build fails. `none:<reason>` is the only opt-out.
- `drive` must never be run against a real device from a test or an agent session.
- `make lint` and `make test` are what CI runs.
