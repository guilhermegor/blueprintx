# Design — Automated tag-driven changelog for service tiers

**Date:** 2026-07-06
**Branch:** `feat/service-tag-changelog`
**Status:** approved (design)

## Problem

The service skeletons (`mvc-service-native-db`, `mvc-service-orm-db`,
`ddd-service-native-db`, `ddd-service-orm-db`) ship a **hand-maintained**
`docs/changelog.md` (Keep-a-Changelog style), while `lib-minimal` ships a
**generated** one (`cz changelog` from git tags, single-sourced via
`--8<-- "CHANGELOG.md"`). The reason services can't use the generated model today
is that **services never create git tags** — `make bump_version` only runs
`poetry version` + `git add pyproject.toml`, so `cz changelog` would have no tags
to group by.

Goal: give the service tiers the same generated, tag-driven changelog as
`lib-minimal`, mirroring the lib's online/offline split.

## Non-goals

- No PyPI/registry publishing for services — they are deployed apps, not packages.
- No `poetry-dynamic-versioning` for services — `pyproject.toml` stays the nominal
  version home (see the "nominal online" note below).
- No change to `lib-minimal`'s own release flow.

## Decisions (approved)

### 1. Tag creation — mirror the lib's online/offline split

- **OFFLINE** (`apply_offline_mode`, no GitHub remote): `make bump_version` becomes
  `cz bump`. `cz bump` reads Conventional Commits since the last tag, computes the
  next semver, updates `pyproject.toml` `version`, commits `bump: X.Y.Z`, and creates
  the annotated tag `vX.Y.Z`. It runs with `--no-verify` to pass the local
  `no-commit-to-branch` / `protect-branch` hooks — the same bypass
  `bin/git_merge_to_main.sh` already uses. `pyproject.toml` and the tag stay in sync
  because `cz bump` writes both.
- **ONLINE** (GitHub remote): a new `release.yaml` workflow (`workflow_dispatch`,
  `version` input) creates the tag `vX.Y.Z` server-side and cuts a **GitHub Release**
  (no PyPI publish). `make bump_version` is **removed online** by the scaffold — the
  same treatment `lib-minimal` gives it via `strip_bump_version`.
- **`pyproject.version` online stays nominal.** The changelog reads *tags*, and after
  PR #41 dropped the docs version badge, nothing reads `pyproject.version` for a
  service (no badge, no wheel). Marked with a `ponytail:` note. If strict sync is ever
  required, the release workflow can open a bump PR — deferred, not built now.

### 2. Changelog page + docs build

- Service `docs/changelog.md` (shared source: `templates/python-common/docs/changelog.md`)
  switches from the hand-maintained page to the include model:
  `--8<-- "CHANGELOG.md"` — identical to `lib-minimal/docs/changelog.md`.
- Seed a root `CHANGELOG.md` in `templates/python-common/` (cz-generated placeholder).
- The service docs workflow (`templates/common/docs_version/docs.yaml`) gains a
  `cz changelog` regeneration step before `mkdocs build --strict`, mirroring
  `lib-minimal/.github/workflows/docs.yaml`. `fetch-depth: 0` is **kept** (now
  load-bearing for `cz changelog`) and its stale "version-badge" comment is corrected.

### 3. commitizen config

Add a `[tool.commitizen]` block to the four service `pyproject.toml` files
(`version_provider = "poetry"`, `tag_format = "v$version"`,
`update_changelog_on_bump = true`, `version = <current>`) — the same block
`lib-minimal` carries, minus `poetry-dynamic-versioning`.

### 4. Recipe relocation (DRY)

- Move the `changelog` recipe from `templates/lib-minimal/make/library.mk` to the
  shared `templates/python-common/Makefile` + `tasks.sh` (all Python tiers now use it),
  including the help-text line. `install_dist_locally` **stays** library-only in
  `library.mk` (genuinely wheel-only).
- Consequence: `templates/python-common/docs/changelog.md` (now the include model)
  becomes identical to `templates/lib-minimal/docs/changelog.md`, so the lib's own copy
  is removed and the shared one serves the lib too (DRY). Verify the lib scaffold copy
  order does not re-introduce a duplicate.

### 5. `release.yaml` single source (copy-list-drift lesson)

Ship `release.yaml` from `templates/python-common/.github/workflows/release.yaml`
(copied by `copy_github_assets` to every Python tier), and have the **lib scaffold
strip it** (lib already ships `release-pypi.yaml` / `release-test-pypi.yaml` and already
performs strips — one more `rm`). One source, no 4× duplication.

### 6. Developer-facing docs (end-user awareness)

Rewrite the `## Releasing` section of `templates/python-common/docs/contributing.md`
(currently documents `make bump_version LEVEL=`) to describe the tag flow:

- **ONLINE:** land code by branching → PR → merge into the default branch; cut a
  release from the `release.yaml` Action (`workflow_dispatch`, `version`), which tags
  `vX.Y.Z` + cuts a GitHub Release; the docs build regenerates the changelog.
- **OFFLINE:** `make new_branch NAME=…` → work → `make bump_version` (now `cz bump`,
  creates the tag) → `make git_merge_to_main`.
- **Highlight prominently that `main` is protected** — no direct commits; all changes
  land via branch → PR (online) or `new_branch` → `git_merge_to_main` (offline).

Keep `CONTRIBUTING.md` (root, authoritative branch/PR policy) in sync if it needs the
protected-main highlight.

### 7. Doc-rot fold-in (PR #41 leftovers)

- `templates/common/docs_version/docs.yaml:33` — correct the stale "version-badge hook"
  comment; `fetch-depth: 0` stays (now used by `cz changelog`).
- `templates/lib-minimal/.github/workflows/docs.yaml:31` — drop "(version badge)" from
  the comment; `fetch-depth: 0` stays (already used by `cz changelog`).

## Files touched (summary)

| File | Change |
|------|--------|
| `templates/python-common/Makefile` | `bump_version` → `cz bump`; add `changelog` recipe (moved from library.mk) |
| `templates/python-common/tasks.sh` | mirror both changes |
| `templates/python-common/docs/changelog.md` | switch to `--8<-- "CHANGELOG.md"` include |
| `templates/python-common/CHANGELOG.md` | new seed |
| `templates/python-common/.github/workflows/release.yaml` | new service release workflow |
| `templates/python-common/docs/contributing.md` | rewrite `## Releasing`; protected-main highlight |
| `templates/{mvc,ddd}-service-*/pyproject.toml` (×4) | add `[tool.commitizen]` |
| `templates/common/docs_version/docs.yaml` | add `cz changelog` step; fix comment |
| `templates/lib-minimal/make/library.mk` | drop `changelog` (keep `install_dist_locally`) |
| `templates/lib-minimal/docs/changelog.md` | remove (now served by shared copy) |
| `templates/lib-minimal/.github/workflows/docs.yaml` | fix comment |
| `bin/scaffold/python_lib_minimal.sh` | strip the generic `release.yaml`; also strip `bump_version` (already does) |
| `templates/python-common/CLAUDE.md` | doc the new tier-shared changelog/release model |

## Testing

- **Scaffold a dev service** (`make dev`) and assert: `[tool.commitizen]` present;
  `make bump_version` invokes `cz bump`; `docs/changelog.md` uses the include; a root
  `CHANGELOG.md` exists; `release.yaml` present online / absent offline.
- **Scaffold the lib** and assert: no generic `release.yaml`; `bump_version` still
  stripped online; `changelog` recipe still available; changelog page unchanged.
- **`act`** the new `release.yaml` and the service `docs.yaml` before pushing
  (act-first lesson).
- Shell lint (`shellcheck` + `bash -n`) on any changed `bin/*.sh`.

## Open risks

- `cz bump --no-verify` offline on a fresh scaffold (0.0.1, no tags): confirm `cz bump`
  succeeds from a tag-less history (bumps from the initial version).
- Lib scaffold copy order: ensure removing `lib-minimal/docs/changelog.md` does not
  leave the lib without the page (shared copy must land).
