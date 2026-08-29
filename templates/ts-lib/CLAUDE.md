# CLAUDE.md

Guidance for Claude Code (or any agent) working in this repository.

## What this is

`${PROJECT_NAME}` is a publishable TypeScript library (npm), scaffolded by BlueprintX's
`ts-lib` skeleton. It ships dual ESM + CommonJS output plus bundled `.d.ts` declarations,
built with `tsc` alone (no bundler).

## Public API discipline

`src/index.ts` is the only barrel that matters: **only what it re-exports is public**.
Add a new export by adding it to `src/index.ts`, not by expecting consumers to deep-import
from `src/*`. Deep imports resolve locally but break at the package boundary — the shipped
`exports` map exposes only `.` (the barrel).

## Build

Three separate `tsc` invocations, one per concern:

- `tsconfig.esm.json` → `dist/esm` (ES modules; `postbuild:esm` drops a `dist/esm/package.json`
  with `"type": "module"` so Node treats those `.js` files as ESM without a bundler).
- `tsconfig.cjs.json` → `dist/cjs` (CommonJS; no marker needed — the root `package.json` has
  no `"type"` field, which Node treats identically to `"type": "commonjs"`. The field is left
  **absent rather than explicit** on purpose: an explicit `"type": "commonjs"` breaks the
  Docusaurus 3.x build in `docs/` with an opaque `sourceType: module` webpack parse error —
  bisected against a vanilla Docusaurus site with only that one field flipped.).
- `tsconfig.types.json` → `dist/types` (declarations only, `emitDeclarationOnly`).

`tsconfig.json` itself is `noEmit: true` — it exists for `type-check`, ESLint's type-aware
parser, and as the shared `extends` base for the three emit configs.

## Testing

Jest with `testEnvironment: 'node'` (this is a library, not a UI — no jsdom). Tests live
next to their subject: `src/example.test.ts` beside `src/example.ts`.

## Before publishing

`npm run pack:smoke` runs `npm pack`, installs the tarball into a throwaway consumer
project, then `require()`s and `import()`s the package **by its package name** (not by
reading `dist/` paths directly) — the only way to catch a broken `exports` map or a file
missing from `"files"` before it reaches npm. Update its require/import checks if you
change the public API.

## Documentation site

`docs/` is a [Docusaurus](https://docusaurus.io) site (docs-only mode, no blog),
built with `npm run docs:build` and deployed to GitHub Pages by
`.github/workflows/docs-deploy.yml` after a non-prerelease GitHub release publishes.
`.github/workflows/docs.yml` runs a build-only check on every push/PR so a broken
sidebar entry or dead link is caught before a release, not after. Versioning uses
Docusaurus's built-in `docs:version` command (run locally, its output committed) —
the analogue of `mike` on the Python skeletons, not something CI cuts automatically.

## Publishing (npm OIDC trusted publishing)

`.github/workflows/release-npm.yml` is `workflow_dispatch`-triggered (mirrors
`release-pypi.yaml`'s shape): tests → version-already-published guard → `npm stage
publish` (holds the package for a maintainer's 2FA approval — no `npm publish`, no
stored `NPM_TOKEN`) → a GitHub release carrying the named `npm pack` tarball. See
`docs/contributing.md` for the one-time bootstrap (npm has no pending-publisher
concept, so the package must be published manually once before a trusted publisher
can be configured for it).

`.github/workflows/pack-smoke.yml` runs on every PR: `npm run pack:smoke` (tarball
install + require/import) plus a Verdaccio rehearsal job that publishes to and
installs from a self-hosted registry — npm's stand-in for Test PyPI, since no
hosted test registry exists and published versions are immutable.

## Do not

- Do not deep-import from `dist/` or `src/` in consumer code — import from the package name.
- Do not add a bundler (tsup/rollup/vite) without first confirming plain `tsc` cannot do the
  job — dual ESM/CJS + declarations is the one case this skeleton already solves without one.
- Do not add an `NPM_TOKEN` secret as a publish fallback — the entire point of OIDC trusted
  publishing is removing the long-lived token. If OIDC breaks, fix the trusted-publisher
  configuration; do not reintroduce a stored token.
- Do not pass `--provenance` to `npm stage publish` — trusted publishing generates
  provenance automatically, and the flag is redundant.
