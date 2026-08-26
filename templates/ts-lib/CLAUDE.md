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
- `tsconfig.cjs.json` → `dist/cjs` (CommonJS; no marker needed — the root `package.json` is
  `"type": "commonjs"`).
- `tsconfig.types.json` → `dist/types` (declarations only, `emitDeclarationOnly`).

`tsconfig.json` itself is `noEmit: true` — it exists for `type-check`, ESLint's type-aware
parser, and as the shared `extends` base for the three emit configs.

## Testing

Jest with `testEnvironment: 'node'` (this is a library, not a UI — no jsdom). Tests live
next to their subject: `src/example.test.ts` beside `src/example.ts`.

## Before publishing

`npm run pack:smoke` runs `npm pack`, extracts the tarball, and `require()`/`import()`s the
result — the only way to catch a broken `exports` map or a file missing from `"files"`
before it reaches npm. Update its require/import checks if you change the public API.

## Do not

- Do not deep-import from `dist/` or `src/` in consumer code — import from the package name.
- Do not add a bundler (tsup/rollup/vite) without first confirming plain `tsc` cannot do the
  job — dual ESM/CJS + declarations is the one case this skeleton already solves without one.
