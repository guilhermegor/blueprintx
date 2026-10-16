# ${PROJECT_NAME}

${PROJECT_DESCRIPTION}

This repo replaces a roughly 50 GB backup of a Ventoy multiboot drive. The repo plus
`sources.manifest` is the backup: every ISO and installer is re-fetched at its latest version,
the persistence image is recreated empty, and the small files that cannot be downloaded live in
`payload/`. On a new machine, `git clone` and `make` rebuild the whole drive tree.

## Usage

```bash
make tools                       # latest Ventoy into .tools/ (also run automatically)
make                             # = make build: download, verify, assemble build/drive
make drive DRY_RUN=1             # preview the sync; nothing is written
make drive                       # asks for the pendrive path, then installs or syncs
make drive TARGET=/media/me/Ventoy
```

Requirements: `bash` >= 4, `curl`, `jq`, `rsync`, `7z`, `sha256sum`, `sudo` (persistence image,
Ventoy install, mounting).

## What `make drive` does

It asks for the pendrive path (a mount point or `/dev/sdX`, or `--target`), resolves it to the
block device and refuses anything that is not a removable disk. Then:

- **Ventoy present** (a `VTOYEFI` partition): sync mode. It adds and updates files, and replaces
  an older version of a manifest entry with the newer one without asking. Every other item on the
  drive that is not in the layout is listed one by one as `delete <path>? [y/N]` (default no;
  `YES_DELETE_EXTRAS=1` skips the questions).
- **Ventoy absent**: it warns that the whole device will be erased, shows the model, size and
  partitions, requires the device name to be typed back, runs `Ventoy2Disk.sh -I`, then syncs.

The write path never runs in Docker: it needs `--privileged` or `--device`, which breaks
removable-device detection and partition re-reads, and Ventoy ships no official image.

## The manifest

`sources.manifest` has one entry per line:
`id|group|folder|kind|source|pattern|checksum|persist|extract`. Nothing is pinned: each kind
resolves the newest upstream version on every run.

| kind | newest version comes from | checksum |
|---|---|---|
| `dirsums` | newest name matching `pattern` in a published checksum file | the same file |
| `github` | latest release asset | the asset `digest` |
| `dirindex` | newest link matching `pattern` in a directory index | `.sha256` sidecar |
| `sfrss` | SourceForge file feed | sidecar, or the md5 in the feed |
| `archive` | archive.org item metadata | the sha1 in the metadata |
| `latesturl` | a URL that always serves the latest installer | `none:<reason>`; re-downloaded when its size changes |
| `windows` | Microsoft's own download API, a fresh time-limited link per run | `none:<reason>` |
| `manual` | nothing resolvable; the build says where to put the file | n/a |

A failing entry is reported and skipped; the rest continue. A missing checksum fails that entry;
`none:<reason>` is the only opt-out. Microsoft sometimes rejects automated requests: download the
ISO by hand into `payload/isos/Windows/` then.

## Payload

Anything under `payload/` is copied verbatim onto the drive tree (for example
`payload/recovery_tools/disk-rescue.sh` or small PDFs). `*.iso *.exe *.zip *.dat *.7z` are
git-ignored; PDFs and scripts are not, so keep this repo private if they are not yours to share.

## Persistence and ventoy.json

The persistence image is created empty by Ventoy's `CreatePersistentImg.sh` (Ventoy publishes no
prebuilt images). It is replaced only when missing or when the configured size changes, and the
sync prints a warning because its saved session data is lost. `ventoy.json` is generated from the
manifest, so the persistence `image` is the path the ISO landed at; `check` fails the build if
any path in it is missing from the tree.

## Development

```bash
make lint     # shellcheck + shfmt
make test     # bats tests/ (network and devices stubbed)
```

## Feature specs

Feature specs live under `.specs/features/`; `.specs/CLAUDE.md` holds the layout rules.

## Releasing

The version is the git tag; there is no hand-bump. Cut a release from the **Release** GitHub
Action (`.github/workflows/release.yml`).
