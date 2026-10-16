# Ventoy USB skeleton (`ventoy-usb`)

Generates a repo that rebuilds a [Ventoy](https://www.ventoy.net) multiboot drive with a fixed
folder layout, downloading the payload at build time. Nothing is copied from an existing drive and
no ISO, installer or persistence image is committed (`.gitignore` excludes `*.iso *.exe *.zip *.dat *.7z`,
`build/` and `.tools/`). The repo plus the manifest replaces a ~50 GB backup of the drive.
Source: `templates/ventoy-usb/`, `bin/scaffold/ventoy_usb.sh` (blueprintx#817, parent #816).

## What it ships

- `sources.manifest`: one line per payload (`id|group|folder|kind|source|pattern|checksum|persist`).
  The drive tree, the downloads and `ventoy/ventoy.json` are all derived from it.
- `bin/<project>`: `layout`, `tools`, `fetch`, `persistence`, `config`, `check`, `build`, `drive`.
- `lib/`: `manifest.sh` (parse and validate), `resolve.sh` (resolvers, download, verify),
  `layout.sh`, `ventoy_config.sh` (`ventoy.json`, persistence image), `drive.sh` (device guard).
- `ventoy-usb.conf`: the scaffold answers (`INCLUDE_WINDOWS`, `INCLUDE_ANDROID`, `PERSISTENCE_SIZE_MB`).
- `payload/`: files copied verbatim onto the tree (owner scripts, small PDFs).
- `tests/*.bats`: layout diff, manifest parsing, resolvers, `ventoy.json` path check, device guard.
  Network is stubbed through `CURL=tests/helpers/curl_stub.sh`.

## Resolvers

No version is ever pinned: each entry resolves the newest upstream version at run time, and an
entry that cannot be resolved fails alone with a message while the rest continue.

| kind | newest version comes from | checksum |
|---|---|---|
| `dirsums` | the newest name matching `pattern` in a published checksum file (GNU, BSD and multi-section formats) | the same file |
| `github` | latest release asset | the asset `digest` the GitHub API reports |
| `dirindex` | newest link matching `pattern` in an HTML directory index | `sidecar:<suffix>` file |
| `sfrss` | SourceForge file feed (`rss?path=`, 100 newest items) | sidecar, or the md5 in the feed |
| `archive` | archive.org item metadata | the sha1 in the metadata |
| `latesturl` | a vendor URL that always serves the latest installer | none published; re-downloaded when `Content-Length` changes |
| `windows` | Microsoft's software-download-connector API (the Fido/Mido flow): a fresh time-limited link per run | none via the API |
| `manual` | nothing resolvable | n/a |

A missing or unparsable checksum fails the entry (fail closed). The only opt-out is an explicit
`none:<reason>`, allowed for `github` (an asset with no API digest), `dirindex`, `latesturl` and
`windows`; `dirsums`, `sfrss` and `archive` always carry a checksum. Hashes are matched by length (sha256, sha1, md5); md5 and sha1 come from the
upstream's own feed and are weaker.

Measured 2026-10-16 (every kind returned its entry live except Windows, which Microsoft rejected, and Clonezilla, whose mirror was down):

| Source | Kind | Newest comes from |
|---|---|---|
| Ubuntu desktop and server 24.04.x, Lubuntu 26.04.x, Kali, Rocky 10, Proxmox VE, Clonezilla, KolibriOS | `dirsums` | checksum file listing |
| Talos, MiniOS, Ventoy, Rufus, RustDesk | `github` | latest release |
| TrueNAS SCALE | `dirindex` | root index, stable releases of any train |
| SystemRescue, Android-x86, PrimeOS, Lineage x86 TV (`lineageos-tv-x86`) | `sfrss` | SourceForge feed |
| tiny11 | `archive` | the maintainer's `tiny11_latest` item |
| AnyDesk, Firefox, Office, Power BI, Revo (and portable) | `latesturl` | vendor URL |
| Windows 11 pt-BR | `windows` | Microsoft API |
| HDT | `manual` | unmaintained, no feed |

Series that are part of an upstream path (Ubuntu 24.04, Lubuntu 26.04, Rocky 10) are the
release line the drive tracks, not a pinned point release.

Windows 11: Microsoft's API sometimes answers `Sentinel marked this request as rejected`. That
is a per-entry failure with a message to download the ISO into `payload/isos/Windows/`. The API
publishes no SHA-256, so the entry carries an explicit `none:<reason>`; TLS to microsoft.com is the
only integrity check.

A `github` `digest` is computed by GitHub: it detects corruption or a swapped download, not a
compromised publisher.

## Persistence and `ventoy.json`

Ventoy publishes prebuilt persistence images in the `ventoy/backend` releases
(`images.zip` holding `persistence_ext4_<N>GB_<label>.dat.7z`; the release notes list their
sha256). The build downloads the one matching the configured size and label, verifies the 7z
against the release notes and extracts it. Only when no published image matches (for example a
size that is not 1, 2 or 4 GB) does it fall back to Ventoy's `CreatePersistentImg.sh -s <MB> -t
ext4 -l <label> -o <path>`, which needs root for a loop device.

The image is replaced only when missing or when the configured size or label changes (the file
name encodes both), with a warning that the saved session data is lost. A newer `ventoy/backend`
release does not replace it: the images are blank templates, and replacing one would wipe the
session for nothing. The folder is spelled `persistance`, as on the original drive.

`ventoy.json` is generated from the manifest, so a persistence `image` is the path the ISO
actually landed at (`/isos/Linux/Desktop/ubuntu-...iso`). `check`, also run by `build`, fails if
any absolute path in the file is missing from the tree. The drive this was measured from had
exactly that defect.

## Trust levels

Each manifest entry names how its download is authenticated, and the build prints the level.

| level | meaning | entries |
|---|---|---|
| `gpg:<fingerprint>:<suffix>:<key url>` | the checksum file's detached signature is verified with `gpg` against a key whose fingerprint is written in the manifest; a missing `gpg`, key or valid signature fails the entry | Ubuntu desktop and server, Lubuntu (Ubuntu CD signing key), Kali |
| `two-origin` | the GitHub digest must equal the sha256 listed on `ventoy.net`; a disagreement fails, and so does an unreachable second origin unless `ALLOW_SINGLE_ORIGIN=1` is set (then it warns) | Ventoy |
| `same-origin-digest` | the checksum comes from the same place as the file: it detects corruption, not a tampered upstream | the other checksum-bearing entries (Rocky, Proxmox, Clonezilla, KolibriOS, TrueNAS, SystemRescue, MiniOS, Talos, Rufus, RustDesk, SourceForge and archive.org entries, the persistence image) |
| `none` | the vendor publishes nothing; explicit `none:<reason>` in the checksum field | vendor installers, Windows 11 |

Rocky's `CHECKSUM` and Proxmox's and Clonezilla's checksum files have no signature or key I could
verify here, so they stay `same-origin-digest`. Ventoy2Disk runs as root on a block device, so
the tarball's two-origin check matters most.

Hardening: every request uses `--proto =https --tlsv1.2`; names taken from upstream must match
`^[A-Za-z0-9._+-]+$` without `..`, and a GitHub download URL must be on `github.com`; archives
extract into a fresh temp dir; the sync deletes a symlink on the drive as the link itself, never follows it, and runs `rm --one-file-system`; checksum lines are matched exactly.

## Tools

`make tools` (also run when Ventoy is missing) downloads the latest Ventoy Linux release into
the git-ignored `.tools/` and verifies the sha256 GitHub publishes for it.

## Writing a drive

`make drive` asks for the pendrive path (or takes `TARGET=`), resolves it to the block device
and refuses anything `lsblk` does not report as a removable disk (`TYPE=disk RM=1`).

- Ventoy present (a `VTOYEFI` partition): **sync**. New and changed files are copied; an older
  version of a manifest entry is deleted automatically once the newer one is in place; every
  other item outside the layout asks `delete <path>? [y/N]` (default no, `YES_DELETE_EXTRAS=1`
  answers yes to all).
- Ventoy absent: **install**. Warns that the whole device is erased, shows model, size and
  partitions, requires the device name to be typed, runs `Ventoy2Disk.sh -I`, then syncs.

Both paths are tested with stubbed `lsblk`, `findmnt` and `Ventoy2Disk.sh`; no test touches a
device. Docker is deliberately not used for this path: it needs `--privileged` or `--device`,
which breaks removable-device detection and the partition re-read, and Ventoy has no official
image.

## Payload

Anything under `payload/` is copied verbatim onto the tree (owner scripts, small PDFs).
`.gitignore` excludes `*.iso *.exe *.zip *.dat *.7z`, not `*.pdf`, so keep a repo that commits
third-party PDFs private.
