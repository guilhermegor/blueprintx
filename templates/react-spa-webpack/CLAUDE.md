# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## What this project is

`${PROJECT_NAME}` is a React 19 + TypeScript + Webpack 5 SPA scaffolded from
BlueprintX using the **react-spa-webpack** skeleton with
**${STATE_MANAGEMENT_VARIANT}** as the state management layer.

## Commands

```bash
npm start          # Webpack dev server with HMR at http://localhost:3000
npm run build      # Production build → dist/
npm run type-check # tsc --noEmit — type errors only, no emit
npm run lint       # ESLint (run `npm run lint:fix` to apply auto-fixes)
```

## Deployment — GitHub Pages

The scaffold ships `.github/workflows/deploy-spa.yml`, which on every push
to `main`:

1. Builds the SPA with `PUBLIC_PATH=/<repo-name>/` so assets resolve under
   the project-site subpath. The same value is inlined into the bundle
   via webpack's `DefinePlugin` as `process.env.PUBLIC_PATH`, so React
   code (specifically `<BrowserRouter basename={...}>`) can read it at
   runtime and route correctly under the subpath.
2. Adds a `404.html` fallback (copy of `index.html`) so client-side
   routes survive Pages's default 404 behaviour.
3. Touches `.nojekyll` to bypass Jekyll's underscore-file filtering.
4. Pushes the `dist/` tree to a `gh-pages` branch via the default
   `GITHUB_TOKEN` (no PAT needed; `contents: write` is enough).

### One-time Pages enablement

**GitHub stopped auto-enabling Pages on `gh-pages` pushes in ~2022.** Even
though the workflow successfully pushes to `gh-pages` on first deploy,
the site returns 404 until Pages itself is explicitly enabled for the
repo. This is a one-time, per-repo step. Pick one:

#### Option A — `gh` CLI (zero clicks)

After your first successful workflow run, run locally:

```bash
gh api -X POST repos/<owner>/<repo>/pages \
  -f 'source[branch]=gh-pages' -f 'source[path]=/'
```

Your local `gh` CLI's token has the `repo` scope that the workflow's
default `GITHUB_TOKEN` lacks, so this works without a PAT. The site
goes live at `https://<owner>.github.io/<repo>/` within ~1 minute.

#### Option B — repo Settings UI

Visit `https://github.com/<owner>/<repo>/settings/pages` →
**Source**: "Deploy from a branch" → **Branch**: `gh-pages` →
**Folder**: `/ (root)` → **Save**.

### Why not `actions/deploy-pages` (modern approach)?

The newer "Deploy from GitHub Actions" path (using `actions/configure-pages`
+ `actions/upload-pages-artifact` + `actions/deploy-pages`) cannot
enable Pages on its own either — the default `GITHUB_TOKEN` lacks the
`administration:write` permission needed to create a Pages site. Both
approaches require the same one-time manual step; the `gh-pages` branch
approach used here has the advantage that pushes work with the default
token and the artifact lives in branch history rather than an opaque
GitHub-managed store.

### Router basename for project sites

Project sites live at `https://<owner>.github.io/<repo>/`. The browser's
`pathname` includes the `/<repo>/` prefix, but client-side routers (e.g.
react-router) compare against the raw pathname — so a `<Route path="/">`
never matches `/<repo>/` and the SPA's own 404 catches every request.

Fix it by passing `basename` to your router. The deploy workflow exposes
the subpath via `process.env.PUBLIC_PATH` (inlined by `DefinePlugin`);
strip the trailing slash because react-router rejects it:

```tsx
// src/routes/MainRouter.tsx
const basename = (process.env.PUBLIC_PATH || '/').replace(/\/$/, '');

export function MainRouter() {
  return (
    <BrowserRouter basename={basename}>
      {/* routes... */}
    </BrowserRouter>
  );
}
```

Locally `PUBLIC_PATH` is unset → defaults to `/` → basename becomes `''`
(react-router's "no prefix"). Under deploy → `PUBLIC_PATH=/<repo>/` →
basename becomes `/<repo>`. Both environments serve the same code.

### Custom domain

If you set a custom domain, add a `CNAME` file at the repo root of the
`gh-pages` branch (or via the Pages settings UI), and the workflow's
`rsync --delete` will preserve it because the action commits to the
existing branch each run rather than rebuilding it from scratch.

## Architecture

Features are organised as **capabilities** under `src/capabilities/<feature>/`.
Each capability owns its full vertical slice.

```
src/
├── capabilities/
│   └── <feature>/
│       ├── domain/
│       │   ├── entities.ts    # Core data shapes — no imports outside domain/
│       │   ├── dto.ts         # Input / output transfer objects
│       │   ├── enums.ts       # Domain enumerations
│       │   └── ports.ts       # Repository / service interfaces
│       ├── application/
│       │   ├── factories.ts   # DTO ↔ entity conversions only
│       │   └── use-cases.ts   # ${STATE_MANAGEMENT_DESC}
│       ├── infrastructure/
│       │   └── api-adapter.ts # Implements ports.ts against the real API
│       ├── ui/
│       │   ├── components/    # Presentational components
│       │   ├── pages/         # Route-level components
│       │   └── styles.module.css
│       ├── context.tsx        # Composition root — wires infra → state → React tree
│       └── index.ts           # Public barrel export
├── shared/
│   └── styles/
│       ├── foundations/       # Design tokens (spacing, colour, typography)
│       └── theme.css          # Dark/light switching via [data-theme] on <html>
├── routes/                    # App-level routing config
├── App.tsx                    # Root component — wires capability providers
└── index.tsx                  # Entry point — global styles, renders App
```

## Layer import rules

Cross-layer imports that violate the table below are caught at lint time via
`eslint-plugin-boundaries`. Run `npm run lint` to verify. Cross-capability
imports must go through the capability's `index.ts` barrel — never import from
internal paths of another capability.

| Layer | May import | Must never import |
|-------|-----------|-------------------|
| `domain/` | Nothing outside `domain/` | application, infrastructure, ui, React |
| `application/` | `domain/` only | infrastructure, ui, React DOM |
| `infrastructure/` | `domain/ports` + external libs | application, ui |
| `ui/` | composition-root hook (`useTaskContext`), `application/`, `domain/` | infrastructure directly |
| composition root (`context.tsx`) | `domain/`, `application/`, `infrastructure/` | ui internals |

The **composition root** (`context.tsx` or `<Name>ContextProvider.tsx`
at the capability root) is the only file that imports from all three
lower layers. It is a *kind of file*, not a fifth layer — the four
layers stay pure, and the composition root sits one level above them
to wire infrastructure → application → React tree. The React equivalent
of Python's `container.py`.

A composition root contains **no business decisions** — only
instantiation, lifecycle, and passing things around. If you find a
business rule in here ("a task completes when secondsRemaining hits
zero"), move it to `application/`; the composition root just wires the
worker's tick stream to a dispatch.

## Module structure

### One class per module

Each source file declares **exactly one** `class`. The filename matches
the class name in kebab-case (`api-adapter.ts` → `ApiAdapter`).

In a function-first codebase this rule mostly governs `infrastructure/`
adapters and any error / state-machine classes. It does **not** apply to:

- **Function components** — small private subcomponents may share a file
  with the primary component if they are not exported.
- **Custom hooks** — one *public* hook per file; private helpers may sit
  beside the public hook.
- **Types, interfaces, enums** — `domain/{entities,dto,enums}.ts`
  deliberately group related declarations by topic; they form a
  vocabulary, not separate concerns.
- **Plain utility functions** — group by topic in a single module
  (`utils/dates.ts`), never wrap them in a utility class.

Private or shared base classes live in their own underscore-prefixed file
(`_base-adapter.ts` exports `BaseAdapter`). Never co-locate a base class
with a concrete subclass in the same module.

**Why:** Single-class files keep `git blame` accurate, let tests target
one class per `__tests__/` file, and remove the implicit coupling that
appears when two classes share a module boundary.

## TypeScript code conventions

Conventions that apply to all TypeScript code in this project — every
layer (`domain/`, `application/`, `infrastructure/`, `ui/`), every file.

### Numeric separators

Use `_` separators in numeric literals **≥ 1000** to keep digit groups
readable. Required for time durations, byte sizes, and any large magic
constant — not optional once a number crosses four digits.

```ts
// ✅ Easy to read at a glance
const ONE_SECOND_MS = 1_000;
const ONE_MEGABYTE = 1_048_576;
const SLOW_REQUEST_TIMEOUT_MS = 30_000;
const MAX_PAYLOAD_BYTES = 5_242_880;

// ❌ Forces digit-counting
const ONE_SECOND_MS = 1000;
const ONE_MEGABYTE = 1048576;
const SLOW_REQUEST_TIMEOUT_MS = 30000;
const MAX_PAYLOAD_BYTES = 5242880;
```

Numeric separators are an **ES2021** feature with universal Node and
modern-browser support — no transpilation concern, no polyfill needed.
The separator is purely syntactic; `1_000 === 1000` is `true` at runtime.

## State management: ${STATE_MANAGEMENT_VARIANT}

${STATE_MANAGEMENT_DESC}

`context.tsx` is the **composition root**: it creates the repository instance
and passes it into the state layer. Components consume state only through the
context hook — never by importing `use-cases.ts` directly.

> **Anti-pattern:** ${STATE_MANAGEMENT_ANTIPATTERN}

## Adding a new capability

Follow this order — skipping steps breaks layer boundaries:

1. Create `src/capabilities/<feature>/domain/{dto,entities,enums,ports}.ts`
2. Write `application/factories.ts` (mappings) then `application/use-cases.ts`
3. Implement `infrastructure/api-adapter.ts` against the port interface
4. Build `ui/{components/,pages/,styles.module.css}`
5. Wire `context.tsx` last — the only file allowed to import from both
   `application/` and `infrastructure/` simultaneously
6. Export the public surface from `index.ts`
7. Add the new provider to `App.tsx`

## `factories.ts` rules

`factories.ts` maps DTOs to entities and entities to response DTOs. Nothing
else. Validation and business logic do not belong here.

```ts
// Correct — pure mapping, no side effects
export function noteFromCreateDTO(dto: NoteCreateDTO): Note {
  return {
    id: crypto.randomUUID(),
    title: dto.title,
    createdAt: new Date(),
    status: NoteStatus.Draft,
  };
}

// Wrong — validation inside a factory; belongs in the use-case
export function noteFromCreateDTO(dto: NoteCreateDTO): Note {
  if (!dto.title) throw new Error('title is required');
  return { id: crypto.randomUUID(), title: dto.title, createdAt: new Date(), status: NoteStatus.Draft };
}
```

## Do / Don't

| Do | Don't |
|----|-------|
| Call `fetch` only inside `infrastructure/` | Call `fetch` from a component or use-case |
| Keep `domain/` free of any React import | Import `useState` or React in `domain/` |
| Accept a port interface as a parameter | Accept a concrete adapter class in use-cases |
| Use `factories.ts` for every DTO ↔ entity conversion | Inline object construction in components |
| Export only the public surface from `index.ts` | Re-export every internal type from `index.ts` |
| Add a new capability for each distinct feature area | Grow one capability into a monolith |
| One class per file; filename matches class name | Co-locate a base class with its subclass in one file |
| Use `_` separators in numeric literals ≥ 1000 (`30_000`, `1_048_576`) | Write 4+ digit literals without separators |

## Testing

| Layer | What to test | How |
|-------|-------------|-----|
| `domain/` | Entity invariants, enum values | Pure unit tests — no mocks |
| `application/factories` | Correct field mapping | Pure unit tests |
| `application/use-cases` | State transitions on success / error | Mock the port interface inline — never the adapter |
| `infrastructure/` | HTTP request / response mapping | Integration tests against MSW or a test server |
| `ui/` | User interactions and rendered output | React Testing Library — behaviour, not internals |

Tests live in `src/capabilities/<feature>/__tests__/`.

## CSS conventions

Global design tokens live in `shared/styles/foundations/` — import via
`shared/styles/foundations/index.css`. Component styles use CSS Modules
(`*.module.css`). Reference tokens via `var(--space-4)` etc. — never use
magic numbers.

`shared/styles/theme.css` controls dark/light switching via
`[data-theme='light']` on `<html>`.

## Custom fonts

The scaffold uses a system font stack. To add a custom font without a Google
CDN request:

```bash
npm install @fontsource/inter
```

```ts
// index.tsx
import '@fontsource/inter/400.css';
import '@fontsource/inter/700.css';
```

Then update `--font-sans` in `shared/styles/foundations/typography.css`.

## Module Federation

If enabled at scaffold time, `webpack.config.js` uses `ModuleFederationPlugin`.
Each capability's `index.ts` is the natural `exposes` entry point. To expose a
new capability, add it to the `exposes` map in `webpack.config.js`.
