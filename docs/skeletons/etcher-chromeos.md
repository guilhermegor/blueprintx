# Etcher ChromeOS flasher skeleton (`etcher-chromeos`)

A Bash CLI starter (`templates/etcher-chromeos/`, `bin/scaffold/etcher_chromeos.sh`) that
rebuilds a ChromeOS-family pendrive. It follows the `bash-cli` skeleton and adds a `flash`
command. The image defines the partition layout (12 partitions on a ChromeOS drive), so
the tool selects, downloads, verifies and flashes; it never builds partitions.

## What it ships

- `bin/<project-name> flash` asks for the pendrive path first (`--target` skips the
  prompt), then the OS (`--os chromeos-flex|fydeos`, default from the `default_os` answer).
- `lib/device.sh` resolves the path to the whole disk and refuses a device that is not
  removable or has mounted partitions. A flash shows model, size and partitions and
  requires typing the device name (`--confirm` answers it non-interactively).
- `lib/flex.sh`, `lib/fydeos.sh`, `lib/flash.sh`, `lib/verify.sh`.
- `bin/fetch_tools.sh` (`make tools`, `make tools_etcher`) fills a git-ignored `.tools/`.
- `Dockerfile` for tests and resolvers only, `tests/cli.bats` with fixtures.

## Research findings

**ChromeOS Flex.** Google publishes
`https://dl.google.com/dl/edgedl/chromeos/recovery/cloudready_recovery2.json`, a list of
entries per channel (`STABLE`, `BETA`, `DEV`, `LTC`, `LTR`). Each carries `url` (a zip),
`zipfilesize`, `file`, `filesize`, and the `sha1` and `md5` of the unzipped `.bin`. The CLI
picks the highest `version` of the requested channel, checks the zip size, unzips, then
checks the image size and SHA-1. The image is about 9.5 GB, so it needs a 16 GB or larger
pendrive; a smaller device is refused before any write.

**FydeOS.** The download page publishes a SHA-256 per variant (for example
`FydeOS_for_PC_v19.0-io-stable.img.xz` and `FydeOS_for_PC_iris_v23.0-SP1-io.bin.zip`) but
the links are chosen on a rendered page, with no unauthenticated "latest" URL or machine
readable index. The CLI therefore takes a file you downloaded plus its published SHA-256
(`--file`, `--sha256`) and verifies the archive before unpacking `.img.xz` or `.zip`.

**Flashing.** balenaEtcher 2.x has no maintained CLI and ships no AppImage (a zip and
`.deb`/`.rpm`). The CLI writes with `bmaptool copy --nobmap` when it is available, else
`dd conv=fsync status=progress`. `make tools_etcher` fetches the GUI, verified against
Etcher's `SHA256SUMS.Linux.x64.txt`, for hand use.

**Trust model for tools.** Whatever runs as root against a block device must be
publisher-attested, so bmaptool is never downloaded. `make tools` uses
`command -v bmaptool` (a distro-signed package: `apt install bmap-tools`,
`dnf install bmap-tools`) and otherwise leaves flashing to plain `dd`. bmaptool's GitHub
releases carry no assets and no checksum, so there is nothing to verify a download against.
The balenaEtcher GUI is the only download, opt-in (`make tools_etcher ALLOW_UNSIGNED_DOWNLOAD=1`
or `--allow-github-digest`), with a warning: it is protected only by Etcher's
`SHA256SUMS.Linux.x64.txt` from the same release, which detects corruption, not a tampered
release. Nothing is pinned: the latest release is resolved at run time, the tag must match
`^v?[0-9]+(\.[0-9]+)*$` and asset names `^[A-Za-z0-9._-]+$` before a URL is built, the
download works in a temporary directory removed on exit, the checksum line must match the
filename exactly, and `curl` is restricted to HTTPS with TLS 1.2 or later.

## Docker

Writing a device from a container needs `--privileged` or `--device` and loses the
removable-device check, so it is not supported. The Dockerfile runs the bats suite only.

## Tests

`tests/cli.bats` stubs `curl`, `lsblk`, `dd` and `sync` on `PATH`. It covers manifest
parsing against a fixture, a checksum mismatch, a non-removable device, a mounted device,
an unconfirmed device, an undersized device and both FydeOS hash outcomes.
