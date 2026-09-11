# CLAUDE.md

> **Audience: BlueprintX contributors only.** This file does **not** ship to
> scaffolded projects — it documents how the `templates/ts-common/` directory
> works inside the BlueprintX repo. Per-project Claude guidance for scaffolded
> TypeScript projects lives in each skeleton's own root `CLAUDE.md`
> (e.g. `templates/react-spa-webpack/CLAUDE.md`), which **is** rendered into
> every scaffolded project via `envsubst`.

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this directory is

`templates/ts-common/` is the **single source of truth for shared tooling** across all BlueprintX TypeScript skeletons. Each tooling file in this directory is copied verbatim (or rendered via `envsubst`) into scaffolded projects by each `bin/scaffold/ts_*.sh` script. This `CLAUDE.md` itself is the exception — see the *Audience* note above.

**Changes here propagate to all TypeScript skeletons on the next scaffold run.**

Almost everything here is *tooling*. **`src/` is the deliberate exception** (blueprintx#436) —
it holds project-agnostic *application code* that is identical across the TS skeletons, mirroring
`templates/python-common/src/utils/`. `python-common` already answered "where does shared TS
source live?" for its own language, and this repo does not get to answer it twice: option A
(mirror the Python precedent) was chosen over keeping each skeleton with its own copy (drift —
the exact problem `check_codespell_sync.sh` polices) or publishing a real npm package for one
interface (correct in the abstract, absurd in practice for this little source). `src/` is copied
into each generated project's own `src/` tree by both `ts_lib.sh` and `ts_react_app.sh` — see
"Files and their roles" below for the two different destinations (ts-lib is a flat package;
react-spa-webpack has a `shared/` layer already reserved for exactly this).

⚠️ **No copy-list drift check exists yet on the TS side.** `bin/ci/check_test_copy_lists.py` is
Python-only (Python's `tests/` copy step). Both `ts_*.sh` scaffolds hand-list what they copy from
`src/`, which is precisely the hand-maintained-`cp`-list pattern that has drifted before
(`python-common/CLAUDE.md`'s `requirements.txt` and `poetry.toml` rows). Left as measured-not-built
for now — a gate here is worth adding once `ts-common/src/` grows past one subpackage, not before.

## Files and their roles

| File / Path | Role |
|-------------|------|
| `src/utils/log-emitter.ts` | `LogEmitter` port + `NULL_EMITTER` (`ts-lib` default — a published package must not log on its own initiative) + `CONSOLE_EMITTER` (`react-spa-webpack` default — `console` is the only destination reachable in a browser without an explicit network call). One file, no internal relative imports — deliberately: a shared file's own relative imports would need `.js` extensions for `ts-lib`'s Node-ESM output (`dist/esm`) and no extension for `react-spa-webpack`'s webpack resolution (`resolve.extensions` has no `.js`→`.ts` alias), and there is no single spelling that satisfies both. Each skeleton's own (non-shared) consumer file imports this module using whatever extension convention that skeleton already uses. No file-writing emitter: impossible in a browser (`jsdom` has no filesystem) and unneeded by measurement (blueprintx#436) |
| `package.json` | Project manifest with `${PROJECT_NAME}` and `${PROJECT_DESCRIPTION}` placeholders; pins React 19, TypeScript 6, Webpack 5, Babel, ESLint 9, Prettier, react-refresh, cross-env |
| `.gitignore` | Node + dist + env patterns |
| `.vscode/settings.json` | Format-on-save (Prettier), ESLint fix-on-save, workspace TypeScript SDK |
| `CONTRIBUTING.md` | Branch naming, commit style, and code-style guide template |
| `.github/workflows/` | GitHub Actions CI — split per-job workflows: `build.yml`, `lint.yml`, `test.yml`, `type-check.yml` on push/PR to `main`, plus `review-threads.yml` (below) |
| `.github/workflows/review-threads.yml` | The answered-review-thread gate (blueprintx#175), on `pull_request` / `pull_request_review` / `pull_request_review_comment`. ⚠️ **Does not carry its own copy of the predicate, and does not fetch one over the network either.** `check_review_threads.py` lives at `templates/common/bin/` — the one shared, language-agnostic surface both language families already copy from — and every `ts_*.sh` scaffold (`ts_react_app.sh`, `ts_lib.sh`) copies it into the generated project's `bin/` at scaffold time, exactly as the Python tiers already do. This job runs that local copy. An earlier revision fetched the script live from `raw.githubusercontent.com` at CI run time; rejected on review as executing unpinned remote code on a runner holding `GITHUB_TOKEN` (see the workflow's own header for the reasoning) |
| `.github/.review-bots.yaml` | This ecosystem's OWN reviewer roster for `review-threads.yml` — data, not logic, so it is genuinely per-ecosystem (unlike the gate script, which is shared). Staged to the checkout root by the workflow before the script runs, because `.github/` is the only ts-common tree every `ts_*.sh` scaffold copies wholesale; there is no scaffold-time `cp` of an arbitrary root-level file the way `python_lib_minimal.sh` copies `python-common/.review-bots.yaml` |
| _(CODEOWNERS, PR template)_ | Sourced from language-agnostic `templates/common/.github/` — copied into every scaffolded project |

## Editing rules

- **`package.json`**: Uses `${PROJECT_NAME}` and `${PROJECT_DESCRIPTION}` placeholders — do not replace them with literal values; they are resolved by `envsubst` during scaffolding. Keep dependency versions pinned to a major range (`^X.0.0`).
- When bumping a dependency here, verify it is compatible with all TypeScript skeletons that consume it.
- Do not add skeleton-specific files here — only files that belong in every TypeScript project.

## State management dependencies (scaffold-time variants)

Dependencies specific to a state management variant are NOT in this `package.json`. The scaffold script (`bin/scaffold/ts_react_app.sh`) adds them at project generation time:

| Variant | Added dependency |
|---------|-----------------|
| Zustand | `zustand ^5.0.0` |
| Redux Toolkit | `@reduxjs/toolkit ^2.0.0`, `react-redux ^9.0.0` |

React Context (default) adds no extra dependencies.
