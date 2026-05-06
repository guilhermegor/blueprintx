# React SPA — DDD Architecture Scaffold

**Date:** 2026-05-06
**Status:** Approved
**Supersedes:** Flat structure in `2026-05-04-react-spa-webpack-template-design.md` (initial scaffold still applies for tooling/discovery; this spec replaces the `src/` layout).

## Goal

Upgrade `templates/react-spa-webpack` from a flat folder structure to a full DDD
(Domain-Driven Design) scaffold that mirrors the vocabulary and layer conventions of the
Python `ddd-service-*` templates. Developers moving between Python services and React SPAs
share the same mental model, folder names, and layer responsibilities.

The scaffold is also Module Federation-ready (Webpack 5 native), allowing capabilities to
be extracted into independently deployed micro-frontends without changing their internal
structure.

---

## Architecture

### DDD per capability

Each business capability owns four layers. Naming is identical to the Python templates:

| Layer | Folder | Python equivalent |
|-------|--------|-------------------|
| Domain | `domain/` | `domain/` |
| Application | `application/` | `application/` |
| Infrastructure | `infrastructure/` | `infrastructure/` |
| UI (frontend-only) | `ui/` | — |
| Composition root | `context.tsx` | `container.py` |
| Public API | `index.ts` | — |

`ui/` has no Python equivalent because services do not render UI. The asymmetry is
expected, not a design flaw.

### Dependency inversion

Infrastructure implements domain ports but is never imported by application or domain.
The composition root (`context.tsx`) is the only file that imports from all layers — it
creates the infrastructure adapter and injects it into application hooks.

```
domain ← application    (application knows only the port interface)
domain ← infrastructure (adapter implements the port)
context.tsx ← all       (sole wiring point — equivalent to container.py)
```

### FSD import discipline via ESLint

`eslint-plugin-boundaries` enforces the dependency rule at lint time:

| Layer | May import from |
|-------|----------------|
| `domain/` | nothing (TypeScript stdlib only) |
| `application/` | `domain/` only |
| `infrastructure/` | `domain/` only |
| `ui/` | `application/` + `domain/` |
| `context.tsx` | all layers (sole composition root) |
| `shared/` | nothing from `capabilities/` |

Cross-capability imports: only via `index.ts` barrel — never internal paths.

---

## Folder Structure

```
src/
├── capabilities/
│   └── example/
│       ├── domain/
│       │   ├── dto.ts              # request/response shapes
│       │   ├── entities.ts         # domain types and interfaces
│       │   ├── enums.ts            # domain constants
│       │   └── ports.ts            # TypeScript interfaces (repository contracts)
│       ├── application/
│       │   ├── use-cases.ts        # React hooks — one hook per use-case
│       │   └── factories.ts        # DTO ↔ entity assemblers
│       ├── infrastructure/
│       │   └── api-adapter.ts      # implements domain port via HTTP/storage
│       ├── ui/
│       │   ├── components/         # capability-scoped components
│       │   ├── pages/              # route-level views for this capability
│       │   └── styles.module.css   # scoped CSS Modules
│       ├── context.tsx             # composition root — wires infrastructure into application
│       └── index.ts                # public barrel — exports only intended consumers
│
├── shared/
│   ├── components/                 # global reusable UI primitives
│   ├── templates/                  # layout shells (persistent chrome)
│   ├── styles/
│   │   ├── global.css              # reset, 62.5% font-size base, body defaults
│   │   ├── foundations/
│   │   │   ├── scale.css           # --neutral-100 … --neutral-900 (color primitives)
│   │   │   ├── primary.css         # brand primitives → semantic aliases
│   │   │   ├── status.css          # --color-success/warning/error/info
│   │   │   ├── text.css            # --color-text-default/muted/disabled
│   │   │   ├── spacing.css         # --space-1 (0.4rem) … --space-8 (6.4rem)
│   │   │   ├── typography.css      # font families, type scale, weights, line-heights
│   │   │   └── index.css           # single @import entry point
│   │   └── theme.css               # [data-theme='light'] overrides — dark-first
│   ├── utils/                      # pure functions, no React dependency
│   └── workers/                    # service workers and background sync
│
├── routes/                         # app-level routing configuration
├── App.tsx
└── index.tsx
```

The flat folders from the initial scaffold (`adapters/`, `contexts/`, `models/`, `pages/`,
`routers/`, `styles/`) are replaced entirely by this structure.

---

## CSS Architecture

### Two-tier token system

`foundations/` files use a primitive → semantic naming pattern that eliminates inline
comments. File names communicate grouping; variable names communicate purpose.

```css
/* foundations/scale.css — primitives named by value */
:root {
  --neutral-100: #f8f9fa;
  --neutral-900: #1a1d27;
}

/* foundations/primary.css — semantics reference primitives */
:root {
  --color-primary-light: var(--green-400);
  --color-primary:       var(--green-600);
  --color-primary-dark:  var(--green-800);
}
```

Swapping a brand color requires changing only the primitive file; all semantic references
update automatically.

### Typography

Defaults to system font stack — zero network dependency, renders the OS's native UI font.
When a custom font is needed, [Fontsource](https://fontsource.org/) is the recommended
path: fonts are self-hosted at build time (no Google CDN, GDPR compliant, no render
blocking).

```ts
// index.tsx — after installing @fontsource/inter
import '@fontsource/inter/400.css'
import '@fontsource/inter/700.css'
```

No Google Fonts `@import` appears in any generated file.

### Spacing

8px grid formalised as named variables. The 62.5% root font-size trick makes the scale
human-readable: `--space-4: 1.6rem` = 16px.

---

## State Management — BlueprintX Menu Option

All three variants generate the same `capabilities/` structure. Only `application/use-cases.ts`
and `context.tsx` differ:

| Option | Implementation | Dependency |
|--------|---------------|------------|
| (A) React Context | `useReducer` + Context provider | none |
| (B) Zustand | store slice per capability | `zustand` |
| (C) Redux Toolkit | RTK slice + RTK Query in `infrastructure/` | `@reduxjs/toolkit` |

Option A is the default.

---

## Module Federation — BlueprintX Menu Option

Offered as a Yes/No question after state management selection. Two clean outputs — no
commented-out blocks in either:

- **No**: minimal `webpack.config.js` (current behaviour)
- **Yes**: fully wired `ModuleFederationPlugin` config; each capability's `index.ts`
  becomes the natural `exposes` entry point

Module Federation (not npm workspaces) is the extraction path when a capability becomes
a standalone deployable unit. The capability's internal structure does not change.

---

## BlueprintX Menu Flow

```
TypeScript
  └── React SPA (Webpack)
        └── State management:
              ├── (A) React Context   ← default
              ├── (B) Zustand
              └── (C) Redux Toolkit
                    └── Module Federation:
                          ├── Yes
                          └── No
```

---

## Files to Create or Modify

### `templates/react-spa-webpack/`

| Path | Action |
|------|--------|
| `src/capabilities/example/domain/dto.ts` | Create |
| `src/capabilities/example/domain/entities.ts` | Create |
| `src/capabilities/example/domain/enums.ts` | Create |
| `src/capabilities/example/domain/ports.ts` | Create |
| `src/capabilities/example/application/use-cases.ts` | Create |
| `src/capabilities/example/application/factories.ts` | Create |
| `src/capabilities/example/infrastructure/api-adapter.ts` | Create |
| `src/capabilities/example/ui/components/.gitkeep` | Create |
| `src/capabilities/example/ui/pages/ExamplePage.tsx` | Create |
| `src/capabilities/example/ui/styles.module.css` | Create |
| `src/capabilities/example/context.tsx` | Create |
| `src/capabilities/example/index.ts` | Create |
| `src/shared/components/.gitkeep` | Create |
| `src/shared/templates/.gitkeep` | Create |
| `src/shared/utils/.gitkeep` | Create |
| `src/shared/workers/.gitkeep` | Create |
| `src/shared/styles/global.css` | Create |
| `src/shared/styles/foundations/scale.css` | Create |
| `src/shared/styles/foundations/primary.css` | Create |
| `src/shared/styles/foundations/status.css` | Create |
| `src/shared/styles/foundations/text.css` | Create |
| `src/shared/styles/foundations/spacing.css` | Create |
| `src/shared/styles/foundations/typography.css` | Create |
| `src/shared/styles/foundations/index.css` | Create |
| `src/shared/styles/theme.css` | Create |
| `src/routes/.gitkeep` | Create |
| `eslint.config.js` | Modify — add `eslint-plugin-boundaries` rules |
| `package.json` | Modify — add `eslint-plugin-boundaries` dev dependency |
| `webpack.config.js` | Modify — MF conditional (two clean outputs) |
| `docs/architecture.md` | Create — layer responsibilities, import rules, Fontsource guide |

### `bin/scaffold/ts_react_app.sh`

Modify to add state management and Module Federation prompts after project name collection.

---

## Verification

1. `npm run lint` catches a forbidden cross-layer import (e.g. `ui/` importing `infrastructure/`)
2. `npm run type-check` passes across all generated files
3. `npm start` renders the example capability without runtime errors
4. All CSS custom properties resolve; `[data-theme='light']` visually inverts the gray scale
5. `npm run build` (MF=No) produces a clean single-bundle output
6. `npm run build` (MF=Yes) produces valid federated output
7. All 6 menu combinations (3 state × 2 MF) scaffold without errors

---

## Out of Scope

- Test runner configuration (no tests in initial scaffold)
- Icon library integration (scaffold components use text labels only)
- Per-capability `package.json` (Module Federation handles extraction, not npm workspaces)
- Google Fonts CDN imports (Fontsource documented, not baked in)
