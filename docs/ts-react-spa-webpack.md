# **React SPA (Webpack)**

A single-page application skeleton built on **React 19**, **TypeScript 5**, **Webpack 5**, and **Babel**. ESLint (flat config, v9) and Prettier are pre-configured. The `src/` directory ships with placeholder subdirectories for every common SPA concern so the project structure is immediately navigable without any initial housekeeping.

This skeleton is intentionally thin on opinions about routing, styling, and state management — those choices belong to the application, not the scaffold.

## Expected layout

```bash
project/
├── src/
│   ├── App.tsx
│   ├── index.tsx
│   ├── adapters/        # external service adapters (API clients, mappers)
│   ├── assets/          # static files imported by components
│   ├── components/      # reusable UI components
│   ├── contexts/        # React context providers
│   ├── models/          # TypeScript interfaces and type definitions
│   ├── pages/           # route-level page components
│   ├── routers/         # routing configuration
│   ├── styles/          # global styles and CSS modules
│   ├── templates/       # layout wrappers and page shells
│   ├── utils/           # pure utility functions
│   └── workers/         # Web Workers and background tasks
├── public/
│   └── index.html       # Webpack HtmlWebpackPlugin template
├── .babelrc             # Babel presets (env, react, typescript)
├── eslint.config.js     # ESLint flat config (v9+)
├── .prettierrc.js       # Prettier config
├── tsconfig.json        # TypeScript strict config, moduleResolution: bundler
├── webpack.config.js    # Webpack 5 dev/prod config, HMR, aliases
├── package.json         # deps + scripts: start, build, typecheck, lint, format
├── .gitignore
├── .vscode/
│   └── settings.json    # format-on-save, ESLint fix-on-save
├── docs/
├── .github/
│   └── workflows/
├── CONTRIBUTING.md
└── LICENSE
```

## Folder descriptions

| Folder / File | Purpose | Expected content |
|---------------|---------|-----------------|
| `src/App.tsx` | Root component | Top-level layout, router outlet |
| `src/index.tsx` | Entry point | `createRoot` + `<App />` mount |
| `src/adapters/` | External integrations | API client wrappers, DTO mappers |
| `src/assets/` | Static resources | Images, fonts, SVGs imported in components |
| `src/components/` | Reusable UI | Stateless or lightly stateful presentational components |
| `src/contexts/` | React contexts | Context definitions and provider components |
| `src/models/` | Type definitions | TypeScript interfaces, enums, type aliases |
| `src/pages/` | Route pages | One file per route; composes components |
| `src/routers/` | Routing | React Router config, guards, lazy imports |
| `src/styles/` | Styles | Global CSS, CSS Modules, design tokens |
| `src/templates/` | Layout shells | Persistent page shells (nav bar, sidebar) |
| `src/utils/` | Utilities | Pure functions with no React dependency |
| `src/workers/` | Background tasks | Web Workers, service workers |
| `public/` | Static assets served as-is | `index.html` (HtmlWebpackPlugin template) |
| `webpack.config.js` | Build config | Entry, output, loaders, HMR, `@/` alias |
| `tsconfig.json` | TypeScript config | Strict mode, `moduleResolution: bundler`, `noEmit: true` |
| `.babelrc` | Transpilation | `@babel/preset-env`, `@babel/preset-react` (automatic runtime), `@babel/preset-typescript` |
| `eslint.config.js` | Linting | Flat config with `@typescript-eslint`, `eslint-plugin-react`, `eslint-plugin-react-hooks` |
| `.prettierrc.js` | Formatting | Single quotes, trailing commas, 100-char width |

## Key configuration notes

### Webpack aliases

`webpack.config.js` maps `@/` → `src/`. Use this for absolute imports instead of relative `../../../` paths:

```ts
import { Button } from '@/components/Button';
```

The same alias is registered in `tsconfig.json` under `paths` so TypeScript resolves it correctly.

### Babel vs TypeScript compiler

`tsconfig.json` sets `"noEmit": true` — TypeScript only type-checks; it never produces output files. Babel handles the actual transpilation via `babel-loader` in Webpack. This is intentional: Babel is faster for large projects and the TypeScript checker runs separately (`npm run typecheck`).

### ESLint flat config

`eslint.config.js` uses the ESLint v9 flat config format. To add rules, extend the exported array — do not create a legacy `.eslintrc.*` file alongside it.

## Rules of thumb

| Concern | Where it lives |
|---------|---------------|
| Reusable UI primitives | `src/components/` |
| Route-level views | `src/pages/` |
| External data fetching | `src/adapters/` |
| Shared TypeScript types | `src/models/` |
| Global React state | `src/contexts/` |
| Pure helpers | `src/utils/` |
| Layout chrome | `src/templates/` |
