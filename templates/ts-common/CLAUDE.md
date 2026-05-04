# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this directory is

`templates/ts-common/` is the **single source of truth for shared tooling** across all BlueprintX TypeScript skeletons. Every file here is copied verbatim (or rendered via `envsubst`) into scaffolded projects by each `bin/scaffold/ts_*.sh` script.

**Changes here propagate to all TypeScript skeletons on the next scaffold run.**

## Files and their roles

| File / Path | Role |
|-------------|------|
| `package.json` | Project manifest with `${PROJECT_NAME}` and `${PROJECT_DESCRIPTION}` placeholders; pins React 19, TypeScript 6, Webpack 5, Babel, ESLint 9, Prettier, react-refresh, cross-env |
| `.gitignore` | Node + dist + env patterns |
| `.vscode/settings.json` | Format-on-save (Prettier), ESLint fix-on-save, workspace TypeScript SDK |
| `CONTRIBUTING.md` | Branch naming, commit style, and code-style guide template |

## Editing rules

- **`package.json`**: Uses `${PROJECT_NAME}` and `${PROJECT_DESCRIPTION}` placeholders — do not replace them with literal values; they are resolved by `envsubst` during scaffolding. Keep dependency versions pinned to a major range (`^X.0.0`).
- When bumping a dependency here, verify it is compatible with all TypeScript skeletons that consume it.
- Do not add skeleton-specific files here — only files that belong in every TypeScript project.
