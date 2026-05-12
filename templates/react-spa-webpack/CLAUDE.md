# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with
code in this repository.

## What this project is

`${PROJECT_NAME}` is a React 19 + TypeScript + Webpack 5 SPA scaffolded from
BlueprintX using the **react-spa-webpack** skeleton with
**${STATE_MANAGEMENT_VARIANT}** as the state management layer.

## Commands

```bash
npm run dev        # Webpack dev server with HMR at http://localhost:3000
npm run build      # Production build → dist/
npm run type-check # tsc --noEmit — type errors only, no emit
npm run lint       # ESLint with auto-fix
```

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
| `ui/` | context hook, `domain/dto` | infrastructure directly |
| `context.tsx` | `application/`, `infrastructure/` | ui internals |

`context.tsx` is the **only** file that imports infrastructure. It is the
React equivalent of Python's `container.py`.

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
