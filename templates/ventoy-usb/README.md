# ${PROJECT_NAME}

${PROJECT_DESCRIPTION}

Rebuilds a [Ventoy](https://www.ventoy.net) multiboot drive from `sources.manifest`:
the folder tree, the latest ISOs, an empty persistence image and `ventoy/ventoy.json`.
Nothing is copied from an existing drive and no payload is committed.

## Usage

```bash
make build                       # download + verify + assemble build/drive
make drive DEVICE=/dev/sdX DRY_RUN=1   # preview; nothing is written
make drive DEVICE=/dev/sdX       # ERASES the device, installs Ventoy, syncs the tree
```

Requirements: `bash` >= 4, `curl`, `jq`, `rsync`, `sha256sum`, `sudo` (persistence image and
drive writes).

`drive` refuses an empty device, a path outside `/dev`, and any device that is not a
removable disk (`lsblk` `RM=1`), then asks you to type the device path back.

## The manifest

`sources.manifest` has one entry per line: `id|group|folder|kind|source|pattern|checksum|persist`.

| kind | meaning |
|---|---|
| `dirsums` | newest name matching `pattern` inside a published checksum file (`sums:<file>`) |
| `github` | latest release asset matching `pattern`; verified against the asset `digest` |
| `pinned` | fixed URL, verified by `sidecar:<suffix>` or `sha256:<hex>` |
| `manual` | never downloaded; place the file under `manual/<folder>/` and `build` copies it |

A missing checksum fails the build. `none:<reason>` is the only explicit opt-out.
Entries marked `# no stable latest` above them are pinned or manual because upstream
publishes no machine-readable newest version.

## Persistence

`persistance/persistence_ext4_<N>GB_<label>.dat` is created empty by Ventoy's own
`CreatePersistentImg.sh` (the tarball comes from the Ventoy release, checksum-verified). The
folder spelling `persistance` matches the original drive.

## ventoy.json

Generated from the manifest. `check` (run by `build`) fails if any path in it, such as a
persistence `image`, is missing from the tree.

## Development

```bash
make lint     # shellcheck + shfmt
make test     # bats tests/ (no network)
```

## Feature specs

Feature specs live under `.specs/features/`; `.specs/CLAUDE.md` holds the layout rules.

## Releasing

The version is the git tag; there is no hand-bump. Cut a release from the **Release** GitHub
Action (`.github/workflows/release.yml`).
