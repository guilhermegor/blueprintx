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

## Files and their roles

| File / Path | Role |
|-------------|------|
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
