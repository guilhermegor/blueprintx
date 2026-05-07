# React SPA (Webpack) — Architecture Guide

## Folder Structure

```
src/
├── capabilities/   # one folder per business capability (≡ Python capabilities/)
├── shared/         # cross-cutting: components, templates, utils, workers, styles
├── routes/         # app-level routing config
├── App.tsx         # root component — wires capability providers
└── index.tsx       # entry point — imports global styles, renders App
```

## DDD Layers (per capability)

| Folder | Imports from | Responsibility |
|--------|-------------|----------------|
| `domain/` | nothing | DTOs, entities, enums, port interfaces |
| `application/` | `domain/` only | hooks (use-cases), DTO↔entity assemblers |
| `infrastructure/` | `domain/` only | API adapters implementing domain ports |
| `ui/` | `application/` + `domain/` | components, pages, scoped CSS Modules |
| `context.tsx` | all layers | composition root — wires infrastructure into application |
| `index.ts` | all layers | public barrel — only intended public exports |

`context.tsx` is the only file that imports infrastructure. It is the React equivalent of Python's `container.py`.

## Import Rules (enforced by ESLint)

Cross-layer imports that violate the table above are caught at lint time via `eslint-plugin-boundaries`. Run `npm run lint` to verify.

Cross-capability imports must go through the barrel `index.ts` — never import from internal paths of another capability.

## Adding a New Capability

1. Create `src/capabilities/<name>/domain/{dto,entities,enums,ports}.ts`
2. Create `src/capabilities/<name>/application/{use-cases,factories}.ts`
3. Create `src/capabilities/<name>/infrastructure/api-adapter.ts`
4. Create `src/capabilities/<name>/ui/{components/,pages/,styles.module.css}`
5. Create `src/capabilities/<name>/context.tsx` (composition root)
6. Create `src/capabilities/<name>/index.ts` (public barrel)
7. Add the new provider to `App.tsx`

## CSS Conventions

- Global design tokens live in `shared/styles/foundations/` — import via `shared/styles/foundations/index.css`
- `shared/styles/theme.css` controls dark/light switching via `[data-theme='light']` on `<html>`
- Component styles use CSS Modules (`*.module.css`). Reference tokens via `var(--space-4)` etc.
- Never use magic numbers — always reference a token variable

## Custom Fonts

The scaffold uses a system font stack. To add a custom font without a Google CDN request:

```bash
npm install @fontsource/inter
```

```ts
// index.tsx
import '@fontsource/inter/400.css';
import '@fontsource/inter/700.css';
```

Then update `--font-sans` in `shared/styles/foundations/typography.css`.

## State Management

The active variant (`context`, `zustand`, or `rtk`) was selected at scaffold time. Only `application/use-cases.ts` and `context.tsx` differ between variants — all other layers are identical.

## Module Federation

If enabled at scaffold time, `webpack.config.js` uses `ModuleFederationPlugin`. Each capability's `index.ts` is the natural `exposes` entry point. To add a new exposed capability, add it to the `exposes` map in `webpack.config.js`.
