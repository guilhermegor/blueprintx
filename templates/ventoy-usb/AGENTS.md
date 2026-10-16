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
- `payload/`: files copied verbatim onto the drive tree.
- `ventoy-usb.conf`: the answers given at scaffold time (persistence size, optional groups).
- `tests/*.bats`: network and devices are always stubbed (`CURL`, `LSBLK`, `FINDMNT`, `VENTOY_DIR`, `DRIVE_MNT`).

## Conventions

- Payloads are never committed: `.gitignore` excludes `*.iso *.exe *.zip *.dat *.7z`, `build/` and `.tools/`.
- Every download is checksum-verified or the build fails. `none:<reason>` is the only opt-out.
- Never pin a version: every entry resolves the latest at run time.
- `drive` must never be run against a real device from a test or an agent session.
- `make lint` and `make test` are what CI runs.
