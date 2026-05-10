# **React SPA (Webpack)**

A single-page application skeleton built on **React 19**, **TypeScript 6**, **Webpack 5**, and **Babel**, structured around **hexagonal / Domain-Driven Design principles**. Each business capability lives in its own `src/capabilities/<name>/` folder with isolated DDD layers. ESLint (flat config, v9) and Prettier are pre-configured; layer boundary violations are caught at lint time by `eslint-plugin-boundaries`.

At scaffold time you are prompted for:

- **State management strategy** — React Context (default, zero deps), Zustand, or Redux Toolkit. Only the chosen variant's files are written.
- **Webpack Module Federation** — optional; replaces `webpack.config.js` with a Module Federation-aware config.

## Expected layout

```
project/
├── src/
│   ├── App.tsx                        # root component — wires capability providers
│   ├── index.tsx                      # entry point — imports global styles, renders App
│   ├── declarations.d.ts             # ambient type declarations for CSS modules
│   ├── capabilities/
│   │   └── <feature>/
│   │       ├── domain/
│   │       │   ├── dto.ts            # input / output DTOs
│   │       │   ├── entities.ts       # domain entity types
│   │       │   ├── enums.ts          # domain enumerations
│   │       │   └── ports.ts          # repository / service port interfaces
│   │       ├── application/
│   │       │   ├── use-cases.ts      # use-case hooks (varies by state management variant)
│   │       │   └── factories.ts      # DTO ↔ entity assemblers
│   │       ├── infrastructure/
│   │       │   └── api-adapter.ts    # port implementation (fetch-based)
│   │       ├── ui/
│   │       │   ├── components/       # capability-scoped presentational components
│   │       │   ├── pages/            # route-level page components
│   │       │   └── styles.module.css # CSS Modules referencing shared design tokens
│   │       ├── context.tsx           # composition root — wires infrastructure into application
│   │       └── index.ts             # public barrel — only intended exports
│   ├── routes/                        # app-level routing configuration
│   └── shared/
│       ├── assets/                    # static files imported by components
│       ├── components/                # cross-capability UI primitives
│       ├── styles/
│       │   ├── foundations/           # design token CSS variables (space, color, type…)
│       │   ├── global.css             # body resets and base rules
│       │   └── theme.css             # dark/light theme switching via [data-theme]
│       ├── templates/                 # persistent layout shells (nav, sidebar)
│       ├── utils/                     # pure functions with no React dependency
│       └── workers/                   # Web Workers and service workers
├── public/
│   └── index.html                     # HtmlWebpackPlugin template
├── .babelrc                           # Babel presets: env, react (automatic), typescript
├── eslint.config.js                   # ESLint v9 flat config with boundaries, hooks, a11y
├── .prettierrc.js                     # Prettier config
├── tsconfig.json                      # strict mode, moduleResolution: bundler, noEmit: true
├── webpack.config.js                  # dev/prod config, HMR, @/ alias, CSS Modules
├── package.json                       # scripts: start, build, type-check, lint, lint:fix
├── .gitignore
├── .vscode/
│   └── settings.json                  # format-on-save, ESLint fix-on-save
├── docs/
├── .github/
│   └── workflows/
│       └── ci.yml                     # type-check → lint → build (parallel jobs)
├── CONTRIBUTING.md
└── LICENSE
```

## Folder descriptions

| Folder / File | Purpose | Expected content |
|---------------|---------|-----------------|
| `src/App.tsx` | Root component | Wraps each capability's provider; no business logic |
| `src/index.tsx` | Entry point | Imports global styles, mounts `<App />` via `createRoot` |
| `src/declarations.d.ts` | Ambient declarations | CSS module types (`*.module.css`, `*.css`) |
| `capabilities/<name>/domain/` | Pure domain model | Entities, DTOs, enums, port interfaces — no I/O |
| `capabilities/<name>/application/` | Use-case layer | Hooks that orchestrate domain + repo; DTO assemblers |
| `capabilities/<name>/infrastructure/` | Adapter layer | `fetch`-based implementations of domain port interfaces |
| `capabilities/<name>/ui/` | Presentation layer | Components, pages, and scoped CSS Modules |
| `capabilities/<name>/context.tsx` | Composition root | The only file that imports infrastructure; wires the capability |
| `capabilities/<name>/index.ts` | Public barrel | Only exports intended for use by other capabilities or `App.tsx` |
| `shared/styles/foundations/` | Design tokens | CSS custom properties: `--space-*`, `--color-*`, `--text-*`, etc. |
| `shared/styles/global.css` | Global resets | Body, box-sizing, base element styles |
| `shared/styles/theme.css` | Theme switching | `[data-theme='light']` / default (dark) overrides |
| `routes/` | Routing config | React Router route definitions, lazy imports, guards |
| `public/index.html` | Webpack template | `<div id="root">` — injected by HtmlWebpackPlugin |

## DDD Layers

### Domain

**What goes here:** pure TypeScript — interfaces, enums, and entity types. No imports from React, infrastructure, or application code.

```ts
// capabilities/example/domain/ports.ts
import type { Note } from './entities';

export interface NoteRepository {
  add(note: Note): Promise<Note>;
  list(): Promise<Note[]>;
  get(id: string): Promise<Note | null>;
}
```

### Application

**What goes here:** use-case hooks that orchestrate domain objects through a port interface. Imports `domain/` only. The shape of the hook depends on the state management variant chosen at scaffold time.

```ts
// capabilities/example/application/use-cases.ts  (React Context variant)
export function useCreateNote(repo: NoteRepository) {
  const [loading, setLoading] = useState(false);
  const execute = useCallback(async (dto: NoteCreateDTO) => { … }, [repo]);
  return { execute, loading };
}
```

```ts
// capabilities/example/application/factories.ts
export function noteFromCreateDTO(dto: NoteCreateDTO): Note { … }
export function noteToResponseDTO(note: Note): NoteResponseDTO { … }
```

### Infrastructure

**What goes here:** concrete implementations of domain port interfaces. Imports `domain/` only — never `application/` or `ui/`.

```ts
// capabilities/example/infrastructure/api-adapter.ts
export class ApiNoteRepository implements NoteRepository {
  async add(note: Note): Promise<Note> { … }
  async list(): Promise<Note[]> { … }
}
```

### UI

**What goes here:** presentational components and pages. Imports `application/` (hooks), `domain/` (types), and the capability's `context.tsx`. Uses CSS Modules that reference shared design token variables.

```tsx
// capabilities/example/ui/pages/ExamplePage.tsx
export function ExamplePage() {
  const { notes, loading } = useNoteContext();
  return <main>{notes.map(n => <ExampleCard key={n.id} note={n} />)}</main>;
}
```

### context.tsx — Composition Root

**What goes here:** the only file in the capability that imports infrastructure. Wires the repository implementation into the application hooks and exposes a React context with a uniform interface across all state management variants.

```tsx
interface NoteContextValue {
  notes: NoteResponseDTO[];
  createNote: (dto: NoteCreateDTO) => Promise<NoteResponseDTO | null>;
  createLoading: boolean;
  createError: Error | null;
  listNotes: () => Promise<void>;
  listLoading: boolean;
  listError: Error | null;
}

export function NoteProvider({ children, repository }: NoteProviderProps) {
  const repo = useMemo(() => repository ?? new ApiNoteRepository(), [repository]);
  const { execute: createNote, loading: createLoading, error: createError } = useCreateNote(repo);
  const { notes, execute: listNotes, loading: listLoading, error: listError } = useListNotes(repo);

  const value = useMemo<NoteContextValue>(
    () => ({ notes, createNote, createLoading, createError, listNotes, listLoading, listError }),
    [notes, createNote, createLoading, createError, listNotes, listLoading, listError],
  );

  return <NoteContext.Provider value={value}>{children}</NoteContext.Provider>;
}
```

The React Context variant exposes separate `createLoading/createError` and `listLoading/listError` because each use-case hook manages its own state. The Zustand and Redux Toolkit variants expose the same interface shape, mapping their unified store state to both pairs.

## Key configuration notes

### Webpack alias

`webpack.config.js` maps `@/` → `src/`. The same alias is declared in `tsconfig.json` under `paths`:

```ts
import { NoteProvider } from '@/capabilities/example';
```

### Babel vs TypeScript compiler

`tsconfig.json` sets `"noEmit": true` — TypeScript only type-checks. Babel handles transpilation via `babel-loader`. Run type-checking separately:

```bash
npm run type-check   # tsc --noEmit
npm run lint         # eslint
npm run build        # webpack --mode production
```

### ESLint boundaries

`eslint.config.js` uses `eslint-plugin-boundaries` to enforce the import rules in the table above. The allowed dependency matrix:

| From | May import |
|------|-----------|
| `domain` | *(nothing)* |
| `application` | `domain` |
| `infrastructure` | `domain` |
| `ui` | `application`, `domain`, `context` |
| `context` | `domain`, `application`, `infrastructure` |
| `barrel (index.ts)` | `domain`, `application`, `ui`, `context` |
| `shared` | `shared` |
| `routes` | `barrel`, `shared` |

### State management variants

| Choice | Files that differ | Extra deps |
|--------|------------------|-----------|
| React Context (default) | `use-cases.ts`, `context.tsx` | none |
| Zustand | `use-cases.ts`, `context.tsx` | `zustand ^5` |
| Redux Toolkit | `use-cases.ts`, `context.tsx` | `@reduxjs/toolkit ^2`, `react-redux ^9` |

All other files (`domain/`, `infrastructure/`, `ui/`, `factories.ts`) are identical across variants.

### CSS design tokens

Global CSS custom properties are defined in `shared/styles/foundations/`. Import the index in any CSS file to access them:

```css
/* styles.module.css */
.card { padding: var(--space-4); color: var(--color-text-default); }
```

Dark/light switching is handled by toggling `data-theme="light"` on `<html>` — no JavaScript class manipulation needed.

## Rules of thumb

| Layer | Responsibility |
|-------|---------------|
| `domain/` | Types and contracts — no runtime behaviour, no I/O |
| `application/` | Orchestration — calls ports, transforms DTOs |
| `infrastructure/` | Side effects — network, storage, external services |
| `ui/` | Presentation — renders state, dispatches actions |
| `context.tsx` | Wiring — the only place infrastructure meets application |
| `index.ts` | API surface — controls what leaks out of a capability |
| `shared/` | Reuse — only code with no single owner goes here |
