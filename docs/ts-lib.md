# **Library (TS, npm-ready)**

A publishable TypeScript library skeleton: dual **ESM + CommonJS** output plus bundled
`.d.ts` declarations, built with `tsc` alone — no bundler, no framework. It ships its own
**Docusaurus** documentation site and an npm-publish CI workflow, so a scaffolded project is
ready to `npm publish` from the first commit, not just ready to run.

Shared tooling (ESLint config layers, Prettier, Husky hooks, `.gitignore`, `.nvmrc`, VS Code
config, the offline git-diff workflow) comes from `templates/ts-common` and is copied
verbatim at scaffold time, the same as `react-spa-webpack`.

---

## 🗂️ Expected layout (after scaffold)

```bash
project/
  src/
    index.ts               # public barrel — only what this file re-exports is public API
    example.ts             # starting-point module; rename or split as the library grows
    example.test.ts
    utils/
      log-emitter.ts        # shared TS source (templates/ts-common) — injectable logging port
  bin/
    write_esm_package_json.sh  # postbuild:esm — stamps dist/esm's own package.json
    smoke_pack.sh              # npm pack smoke test (unpacks the tarball, checks it resolves)
  docs/                    # Docusaurus site source
    index.md · usage.md · examples.md · faq.md · contributing.md
  .github/workflows/
    docs.yml               # build the Docusaurus site on push
    docs-deploy.yml        # deploy the built site (GitHub Pages)
    pack-smoke.yml         # npm pack + install smoke test on every push
    release-npm.yml        # npm OIDC trusted-publishing release
  tsconfig.json             # base config (type-check, IDE)
  tsconfig.esm.json          # ESM build target
  tsconfig.cjs.json          # CJS build target
  tsconfig.types.json        # .d.ts-only build target
  eslint.config.mjs         # vendor allowlist + function-length + catch-safety rules
  jest.config.cjs
  babel.config.test.cjs
  docusaurus.config.js
  sidebars.js
  package.json
  .gitignore
  .vscode/
  CONTRIBUTING.md
  LICENSE
```

---

## 📁 Folder Descriptions

| Folder | Purpose | Expected Content |
|--------|---------|-------------------|
| `src/` | Library source | `index.ts` barrel plus every module it re-exports; the ONLY public surface is what `index.ts` exports — a deep import resolves locally but breaks once published, since the shipped `exports` map exposes only `.` |
| `src/utils/` | Shared TS helpers | `log-emitter.ts` (from `templates/ts-common`) — a published library must never write to a host's console on its own initiative, so every call site accepts an injectable `LogEmitter` defaulting to a no-op |
| `bin/` | Shell helpers | `write_esm_package_json.sh` (stamps `dist/esm/package.json` so Node resolves ESM output correctly), `smoke_pack.sh` (the `npm pack` smoke test) |
| `docs/` | Docusaurus site source | `index.md`, `usage.md`, `examples.md`, `faq.md`, `contributing.md` — rendered by `docs.yml`/`docs-deploy.yml`, not by `mkdocs` |
| `.github/workflows/` | CI/CD pipelines | Docs build + deploy, `npm pack` smoke test, and the npm OIDC publish workflow |

---

## 🚀 Starting point

The generated `src/index.ts` re-exports the starter module — this barrel is the entire
public API surface:

```typescript
// src/index.ts
export { greet } from "./example";
```

```typescript
// src/example.ts
export function greet(str_name: string): string {
	return `Hello, ${str_name}!`;
}
```

```typescript
// src/example.test.ts
import { greet } from "./example";

test("greet returns a greeting for the given name", () => {
	expect(greet("World")).toBe("Hello, World!");
});
```

---

## 🛠️ Build model

Unlike `react-spa-webpack` (one Webpack bundle), `ts-lib` builds **three separate `tsc`
targets** so the package works from both `import` and `require`:

| Script | `tsconfig` | Produces |
|--------|------------|----------|
| `npm run build:esm` | `tsconfig.esm.json` | `dist/esm/` — ES modules; `postbuild:esm` stamps its own `package.json` (`{"type":"module"}`) so Node resolves it as ESM regardless of the package root's own `type` field |
| `npm run build:cjs` | `tsconfig.cjs.json` | `dist/cjs/` — CommonJS; no per-file marker needed (absent `"type"` already means `"commonjs"` to Node) |
| `npm run build:types` | `tsconfig.types.json` | `dist/types/` — bundled `.d.ts` declarations |
| `npm run build` | (runs all three) | The full `dist/` shipped to npm — declared in `package.json`'s `exports` map |

`npm run pack:smoke` (`bin/smoke_pack.sh`) is the should-fail witness for the whole build:
it runs `npm pack`, installs the resulting tarball into a throwaway project, and imports it —
proving the `exports` map actually resolves, which a passing `tsc`/`jest` run alone cannot.

---

## 🛡️ Tooling (inherited from `ts-common`, plus its own layers)

| Tool | Role | Config file |
|------|------|-------------|
| **TypeScript** (`tsc`, strict mode) | Type-check + the three build targets above | `tsconfig*.json` |
| **ESLint** | Lint | `eslint.config.mjs` — a per-layer **vendor allowlist** (deny-by-default, mirrors the Python skeletons' `.layer-policy.yaml`), `max-lines-per-function: 60` (mirrors `check_function_length.py`), and two type-aware catch-safety rules closing the gap plain `strict: true` leaves on `.catch(cb)` callbacks |
| **Prettier** | Formatting | `.prettierrc.mjs` |
| **Jest** | Test runner | `jest.config.cjs` + `babel.config.test.cjs` |
| **Husky + lint-staged** | Git hooks | `.husky/` (from `ts-common`) + `lint-staged.config.mjs` |
| **Docusaurus** | Docs site | `docusaurus.config.js` + `sidebars.js`; `npm run docs:start` / `docs:build` |
| **npm OIDC publish** | Release | `.github/workflows/release-npm.yml` — trusted publishing, no long-lived npm token stored as a secret |

---

## 🔄 Typical workflow

1. Add exported functions/classes under `src/`, and add each to `src/index.ts`'s barrel —
   nothing else is part of the published API.
2. Add a new third-party import to `eslint.config.mjs`'s `VENDOR_POLICY` for the importing
   layer, with a reason — an unlisted vendor fails lint, not silently.
3. Write the matching `*.test.ts` alongside the module (Jest picks it up automatically).
4. `npm run build && npm run pack:smoke` before publishing — the smoke test is the one
   check that proves the shipped `exports` map actually resolves.
5. Keep `docs/*.md` in sync with the public API; `npm run docs:start` serves it locally.

---

## 💡 Example feature addition

```typescript
// src/math-utils.ts
export function add(int_a: number, int_b: number): number {
	return int_a + int_b;
}
```

```typescript
// src/math-utils.test.ts
import { add } from "./math-utils";

test("add returns the sum of two positive integers", () => {
	expect(add(2, 3)).toBe(5);
});

test("add returns the correct sum for a negative operand", () => {
	expect(add(-1, 1)).toBe(0);
});
```

```typescript
// src/index.ts — export it from the barrel, or it never ships
export { add } from "./math-utils";
```
