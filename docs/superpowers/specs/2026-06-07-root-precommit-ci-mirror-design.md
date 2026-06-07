# Root pre-commit — local mirror of Scaffold Checks CI

**Date:** 2026-06-07
**Status:** Design approved, pending spec review
**Scope:** Concern (A) only — BlueprintX's *own* repo. The scaffolded-project
pre-commit (`templates/python-common/.pre-commit-config.yaml`) and every skeleton
layout are **out of scope and untouched**.

## Problem

PR #30's CI failed on the *Spell check* job because the new Portuguese backlog doc
tripped codespell. Nothing runs codespell (or any CI check) locally before a push,
so the only feedback loop is a full CI round-trip. The BlueprintX root repo has **no
pre-commit config, no Makefile `precommit` target, and no `.vscode/`** — the only
pre-commit that exists ships *into scaffolded projects*, not this repo.

## Goal

Give the BlueprintX repo a local pre-commit that mirrors `.github/workflows/scaffold-checks.yml`
so the same failures surface before commit/push. CI and local must run **identical
logic** — no second copy of any check to drift.

## Boundary (explicit)

| Concern | In scope? | Where it lives |
|---------|-----------|----------------|
| (A) BlueprintX repo's own pre-commit | **Yes** | repo root (`/.pre-commit-config.yaml`, `/.codespellrc`), helpers in root `bin/` |
| (B) Scaffolded projects' pre-commit | No | `templates/python-common/.pre-commit-config.yaml` — unchanged |
| Skeleton layout structures | No | `templates/*/` — unchanged |

## Architecture — `bin/ci/` as the single source of truth

CI already delegates three checks to scripts under `bin/ci/`
(`validate_meta.sh`, `check_version_sync.sh`, `smoke_test.sh`). This design extends
that established pattern: every check the pre-commit mirrors is a `bin/ci/*.sh`
script that **both** the workflow and the hook invoke. The pre-commit config and the
workflow YAML become thin callers; the logic has one home.

### New shared scripts (`bin/ci/`)

| Script | Logic | Replaces inline step in |
|--------|-------|-------------------------|
| `check_spelling.sh` | `codespell docs/ templates/ --config=.codespellrc` | `spell-check` job |
| `check_shell.sh` | `find bin -name '*.sh' -print0 \| xargs -0 shellcheck --severity=warning` | `lint-shell` job |
| `check_docs_build.sh` | `mkdocs build --strict` (via `poetry run` when available, else bare) | `docs-build` job |

Each script: `#!/usr/bin/env bash`, `set -euo pipefail`, resolves repo root from
`BASH_SOURCE`, `cd`s to root, runs the one command. Single responsibility, no args.

### New config — `/.codespellrc`

```ini
[codespell]
skip = *.png,*.svg,*.ico,*.jpg,*.json,*.lock,*.po,*.pyc
quiet-level = 3
ignore-words-list = nd,fpr,strat,enty,filetest,nome,nomes,caracteres,prefere,atual,ZAR,fro,hsi,HSI,WEGE,zar,SMLL,Classe,classe,erro,serie,emiss,TERMO,termo,INDX
```

This is the curated list **currently inline** in the workflow. Once it moves here,
the inline `--ignore-words-list` / `--skip` / `--quiet-level` flags are deleted from
the YAML and `check_spelling.sh` passes `--config=.codespellrc`. One list, zero drift.
(`docs/` + `templates/` stay as CLI path args — codespellrc has no "paths" key.)

> Note: this is distinct from `templates/python-common/.codespellrc`, which ships into
> scaffolded projects and serves a different vocabulary. The two are intentionally separate.

### Workflow refactor — `scaffold-checks.yml`

Three jobs change from inline `run:` to a script call:

- `lint-shell` → `run: bash bin/ci/check_shell.sh`
- `docs-build` → `run: bash bin/ci/check_docs_build.sh` (keeps the pip-install-mkdocs step)
- `spell-check` → `run: bash bin/ci/check_spelling.sh` (keeps the pip-install-codespell step)

`validate-meta`, `version-sync`, `dry-run-smoke`, `typecheck-ts` are unchanged.

## `/.pre-commit-config.yaml`

Three layers:

**1. Pinned upstream `pre-commit/pre-commit-hooks` (v5.0.0)** — generic hygiene, no
custom logic:
- `trailing-whitespace` (`--markdown-linebreak-ext=md`)
- `end-of-file-fixer`
- `check-yaml` (`--unsafe` — workflow files use tags)
- `check-json`, `check-toml`
- `check-merge-conflict`
- `detect-private-key`
- `check-added-large-files` (`--maxkb=500`)
- `no-commit-to-branch` (protects `main`, matches CONTRIBUTING's rule)

**2. Pinned `commitizen` (v4.x) + `gitlint` (v0.19.x)** — `commit-msg` stage,
Conventional Commits enforcement. Self-contained pre-commit-managed envs (no poetry dep needed).

**3. `repo: local`** — the shared scripts, all `language: system`,
`pass_filenames: false`:

| id | entry | stage | notes |
|----|-------|-------|-------|
| `codespell` | `bash bin/ci/check_spelling.sh` | commit | full docs/+templates/ scan, matches CI exactly |
| `shellcheck` | `bash bin/ci/check_shell.sh` | commit | `files: ^bin/.*\.sh$` to scope the trigger |
| `validate-meta` | `bash bin/ci/validate_meta.sh` | commit | `files: skeleton\.meta$` |
| `version-sync` | `bash bin/ci/check_version_sync.sh` | commit | `always_run: true` |
| `mkdocs-strict` | `bash bin/ci/check_docs_build.sh` | commit | runs every commit (user choice) |

**Deliberately CI-only (YAGNI locally):** `dry-run-smoke` (6× scaffold) and
`typecheck-ts` (npm install) are too heavy for a commit hook. They stay in CI.

## Makefile + tasks.sh

Add to both (logic stays thin — recipes just call pre-commit). Follow the cvm
`init: venv precommit` bootstrap pattern, adapted to BlueprintX's existing
`init_venv` target name:

```make
init: init_venv precommit

precommit:
	@poetry run pre-commit install
	@poetry run pre-commit install --hook-type commit-msg

lint:
	@poetry run pre-commit run --all-files
```

So a fresh clone runs `make init` once to bootstrap the venv **and** wire the
`commit` / `commit-msg` / pre-push hooks. The existing `init_venv` target stays as-is
(callable on its own); `init` is the new aggregate. `tasks.sh` gets the mirror
functions (`init`, `precommit`, `lint`) + case entries + help lines, matching the
Makefile one-to-one (cvm keeps these two in lockstep).

## `.vscode/`

Scaled-down mirror of cvm (no Python-testing keys — BlueprintX root is not a Python app):

- **`settings.json`**: `files.insertFinalNewline`, `files.trimTrailingWhitespace`,
  `files.associations` for `.gitlint` → `ini`. No interpreter/pytest keys.
- **`tasks.json`**: shell tasks with `make … || ./tasks.sh …` fallback for
  `new`, `preview`, `dry-run`, `lint`, `precommit`, `mkdocs_server`, `help`.

## Dependencies

`pre-commit` and `commitizen` are already in `pyproject.toml` dev deps. `gitlint`,
`shellcheck`, `codespell`, `mkdocs-material` are provided by pre-commit-managed envs,
brew/system, or the docs group — no new poetry deps required. A `.gitlint` config file
is added at root (Conventional-Commits-compatible) if gitlint's defaults need tuning.

## Testing / verification

1. `poetry run pre-commit run --all-files` passes clean on current tree.
2. Re-introduce a known typo in a docs file → `codespell` hook blocks the commit.
3. Break a shell script (unquoted var) → `shellcheck` hook blocks.
4. Mismatch `pyproject.toml` vs `blueprintx.sh` version → `version-sync` hook blocks.
5. Non-conventional commit message → `commitizen`/`gitlint` block at `commit-msg`.
6. CI still green after the workflow refactor (scripts produce identical output).

## Out of scope / non-goals

- No changes to any `templates/*` skeleton or the scaffolded-project pre-commit.
- No mirroring of the dry-run smoke matrix or TS typecheck locally.
- No new release/packaging manifests.
```