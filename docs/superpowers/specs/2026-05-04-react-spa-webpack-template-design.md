# React SPA Webpack Template — Design Spec

**Date:** 2026-05-04
**Status:** Approved

## Goal

Add a `react-spa-webpack` skeleton to BlueprintX that scaffolds a React 19 + TypeScript 6
single-page application using a hand-rolled Webpack 5 + Babel configuration. The skeleton
mirrors the layout of an existing reference project and is wired into the interactive menu
via a new discovery-based skeleton system.

## Discovery System

Replace the hard-coded language/skeleton menus in `blueprintx.sh` with auto-discovery:

- Any `templates/*/skeleton.meta` file marks that directory as a scaffold target.
- `skeleton.meta` is a shell-sourceable KEY=VALUE file with four fields:

```
language=typescript
display_name=React SPA (Webpack)
description=React 19 + TypeScript 6 + Webpack 5 + Babel + ESLint + Prettier
scaffold=bin/scaffold/ts_react_app.sh
```

- `prompt_language` is built by de-duplicating `language=` values across all discovered metas.
- `prompt_skeleton` shows only skeletons whose `language` matches the user's choice.
- `create_project` dispatches to the `scaffold=` path from the matching meta.
- Directories without `skeleton.meta` (`python-common`, `ts-common`, `licenses`) are ignored.

The three existing Python skeletons each receive a `skeleton.meta` file; their content is
otherwise unchanged.

## New Files

### `templates/react-spa-webpack/`

Verbatim copy of the reference layout (node_modules and package-lock.json excluded):

```
react-spa-webpack/
├── skeleton.meta
├── public/
│   └── index.html
├── src/
│   ├── App.tsx
│   ├── index.tsx
│   ├── adapters/.gitkeep
│   ├── assets/.gitkeep
│   ├── components/.gitkeep
│   ├── contexts/.gitkeep
│   ├── models/.gitkeep
│   ├── pages/.gitkeep
│   ├── routers/.gitkeep
│   ├── styles/.gitkeep
│   ├── templates/.gitkeep
│   ├── utils/.gitkeep
│   └── workers/.gitkeep
├── .babelrc
├── eslint.config.js
├── .prettierrc.js
├── tsconfig.json
└── webpack.config.js
```

None of these files contain project-specific placeholders — they are copied verbatim.

### `templates/ts-common/`

Shared assets copied into every TypeScript skeleton (mirrors `python-common` role):

```
ts-common/
├── .gitignore
├── .vscode/
│   └── settings.json
├── CONTRIBUTING.md
└── package.json          ← uses ${PROJECT_NAME} and ${PROJECT_DESCRIPTION} placeholders
```

`package.json` is rendered via `envsubst` at scaffold time.

### `bin/scaffold/ts_react_app.sh`

Scaffold script following the same sequence as Python scripts:

1. `validate_inputs` — checks `PROJECT_ROOT` and `PROJECT_NAME`
2. `resolve_github_username` — env var → `gh` CLI → interactive prompt
3. `create_directory_structure` — `mkdir -p` for `src/`, `public/`, `assets/`, `bin/`, `docs/`, `.github/workflows/`, `.vscode/`
4. `copy_skeleton_files` — copies `templates/react-spa-webpack/` verbatim
5. `copy_common_templates` — `envsubst` renders `ts-common/package.json`; copies `.gitignore`, `.vscode/settings.json`, `CONTRIBUTING.md`, license file
6. `prompt_git_remote_setup` — optional `git init`, `gh repo create`, branch protection

## Modified Files

### `bin/blueprintx.sh`

- `prompt_language` — replaced with discovery loop over `templates/*/skeleton.meta`; renders coloured menu from distinct `language=` values.
- `prompt_skeleton(lang)` — replaced with filtered discovery loop for the chosen language.
- `create_project` — dispatches via `scaffold=` field from the matched `skeleton.meta`.
- `show_skeleton_structure` — reads `description=` from `skeleton.meta` as fallback; existing hand-written previews for Python skeletons are preserved.

### Existing Python skeleton directories

Each receives a `skeleton.meta` file:

| Directory | language | display_name |
|-----------|----------|--------------|
| `ddd-service-native-db` | python | DDD Service (Native DB) |
| `ddd-service-orm-db` | python | DDD Service (ORM) |
| `lib-minimal` | python | Library (Minimal) |

## Naming rationale

`react-spa-webpack` was chosen over `ts-react-app` or `react-webpack-babel` because:
- The SPA qualifier distinguishes it from SSR/SSG solutions (Next.js).
- The Webpack qualifier distinguishes it from Vite-based setups.
- Babel is an implementation detail of the Webpack config, not a user-facing choice.

## Out of scope

- No CSS/styling layer (CSS Modules, styled-components) — left for the developer to add.
- No test runner — the reference project has no tests configured.
- No MkDocs site for TS projects — can be added as a follow-on skeleton.
