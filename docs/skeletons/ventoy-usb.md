# Ventoy USB skeleton (`ventoy-usb`)

Generates a repo that rebuilds a [Ventoy](https://www.ventoy.net) multiboot drive with a fixed
folder layout, downloading the payload at build time. Nothing is copied from an existing drive and
no payload is committed (`.gitignore` excludes `*.iso *.exe *.zip *.dat` and `build/`).
Source: `templates/ventoy-usb/`, `bin/scaffold/ventoy_usb.sh` (blueprintx#817, parent #816).

## What it ships

- `sources.manifest`: one line per payload (`id|group|folder|kind|source|pattern|checksum|persist`).
  The drive tree, the downloads and `ventoy/ventoy.json` are all derived from it.
- `bin/<project>`: `layout`, `fetch`, `persistence`, `config`, `check`, `build`, `drive`.
- `lib/`: `manifest.sh` (parse and validate), `resolve.sh` (resolvers, download, verify),
  `layout.sh`, `ventoy_config.sh` (`ventoy.json`, persistence image), `drive.sh` (device guard).
- `ventoy-usb.conf`: the scaffold answers (`INCLUDE_WINDOWS`, `INCLUDE_ANDROID`, `PERSISTENCE_SIZE_MB`).
- `manual/`: overlay for payloads that cannot be fetched; `build` copies it onto the tree.
- `tests/*.bats`: layout diff, manifest parsing, resolvers, `ventoy.json` path check, device guard.
  Network is stubbed through `CURL=tests/helpers/curl_stub.sh`.

## Resolvers

| kind | "latest" comes from | checksum |
|---|---|---|
| `dirsums` | the newest name matching `pattern` (`sort -V`) in a published checksum file | the same file (GNU, BSD and multi-section `CHECKSUMS.TXT` formats) |
| `github` | the newest release asset matching `pattern` | the asset `digest` the GitHub API reports (`sha256:...`) |
| `pinned` | none: a fixed URL, with a `# no stable latest` note above it | `sidecar:<suffix>` file or `sha256:<hex>` |
| `manual` | never downloaded; the build prints where to put the file | n/a |

A missing or unparsable checksum fails the build (fail closed). The only opt-out is an explicit
`none:<reason>`. `dirsums` and `github` entries cannot opt out.

Measured sources (2026-10-15):

| Source | Kind | Latest-ness | Checksum |
|---|---|---|---|
| Ubuntu desktop / server 24.04.x | `dirsums` | newest point release | `SHA256SUMS` |
| Lubuntu 26.04.x | `dirsums` | newest point release (series pinned in the URL) | `SHA256SUMS` |
| Kali installer | `dirsums` | `current/` always the newest | `SHA256SUMS` |
| Clonezilla stable | `dirsums` | newest in `clonezilla-live/stable/` | `CHECKSUMS.TXT` |
| Rocky 10 boot | `dirsums` | newest 10.x | `CHECKSUM` (BSD format) |
| Proxmox VE (x86_64) | `dirsums` | newest | `SHA256SUMS` |
| Talos `metal-amd64.iso` | `github` | latest release | asset `digest` |
| MiniOS standard and ultra | `github` | latest release | asset `digest` |
| Ventoy (installer + persistence script) | `github` | latest release | asset `digest` |
| Rufus, RustDesk (Windows) | `github` | latest release | asset `digest` |
| SystemRescue 13.02 | `pinned` | no machine-readable newest feed | `.sha256` sidecar |
| TrueNAS SCALE 25.10.7 | `pinned` | one listing mixes every train and beta | `.sha256` sidecar |
| Windows 11, tiny11, Android-x86, Lineage x86, PrimeOS | `manual` | no stable URL or no checksum | n/a |
| HDT, KolibriOS (nightly is a `.7z`) | `manual` | unmaintained or archive-only | n/a |
| AnyDesk, Firefox, Office, Power BI, Revo | `manual` | per-session or checksum-less downloads | n/a |
| Owner scripts (`dotfiles`, `disk-rescue.sh`) | `manual` | not public artifacts | n/a |

tiny11 is a third-party rebuild of Windows with no signed checksum, so it is never fetched.
The Proxmox entry selects the x86_64 ISO; the drive this was measured from carried the arm64 one.

A `github` `digest` is computed by GitHub, so it detects a corrupted or swapped download but
does not attest the publisher. Where a project also signs its release, verifying that signature
is a stronger follow-up.

## Persistence and `ventoy.json`

The persistence image is created empty by Ventoy's own `CreatePersistentImg.sh -s <MB> -t ext4
-l casper-rw -o <path>` (root is required: it uses a loop device). It is never downloaded.
The folder is spelled `persistance`, as on the original drive.

`ventoy.json` is generated from the manifest, so a persistence `image` is the path the ISO
actually landed at. `check` (also run by `build`) fails if any absolute path in the file is
missing from the tree. The drive this skeleton was measured from had exactly that defect: its
persistence entry pointed at `/isos/Linux/ubuntu-...iso` while the ISO lived in `Desktop/`.

## Writing a drive

`make drive DEVICE=/dev/sdX` (add `DRY_RUN=1` to preview). It refuses an empty device, a path
outside `/dev`, and anything `lsblk` does not report as a removable disk (`TYPE=disk RM=1`), then
requires the device path to be typed back before it runs `Ventoy2Disk.sh -I` and syncs the tree.
The guard is tested with a stubbed `lsblk`; the write path is never run in tests.
