# ${PROJECT_NAME}

[![Project Status: Active](https://www.repostatus.org/badges/latest/active.svg)](https://www.repostatus.org/#active)
![Node](https://img.shields.io/badge/node-%E2%89%A520-339933?logo=node.js&logoColor=white)
![TypeScript](https://img.shields.io/badge/typescript-5.x-3178C6?logo=typescript&logoColor=white)
![React](https://img.shields.io/badge/react-19-61DAFB?logo=react&logoColor=white)
![Webpack](https://img.shields.io/badge/webpack-5-8DD6F9?logo=webpack&logoColor=white)
[![Linting](https://img.shields.io/badge/linting-eslint_|_stylelint_|_prettier-blue)](https://eslint.org)
![License](https://img.shields.io/badge/license-${PROJECT_LICENSE}-green.svg)
![Open Issues](https://img.shields.io/github/issues/${GITHUB_USERNAME}/${PROJECT_NAME})
![Contributions Welcome](https://img.shields.io/badge/contributions-welcome-darkgreen.svg)

${PROJECT_DESCRIPTION}

## ✨ Key Features

### 🧭 Pages & Routes
- [Page placeholder 1](#)
- [Page placeholder 2](#)
- [Page placeholder 3](#)

### 🧩 Capabilities (vertical slices)
- [Capability placeholder 1](#)
- [Capability placeholder 2](#)
- [Capability placeholder 3](#)

### 🔁 State Management
- Variant: **${STATE_MANAGEMENT_VARIANT}** — see `src/capabilities/<feature>/context.tsx`

### 🎨 UI & Accessibility
- [a11y / i18n / theming placeholder](#)
- [Design-system placeholder](#)

### ⚡ Performance
- [Code-splitting / lazy-loading placeholder](#)
- [Bundle-analysis placeholder](#)

### 🧪 Testing
- Unit / component: **Jest + React Testing Library**
- End-to-end: **Playwright** (chromium)

## 🚀 Getting Started

### Prerequisites
- Node ≥ 20
- npm (bundled with Node) — pnpm / yarn also work
- A modern browser for development (Chrome, Firefox, Safari)

### Installation
```bash
git clone https://github.com/${GITHUB_USERNAME}/${PROJECT_NAME}.git
cd ${PROJECT_NAME}
npm install
npm run dev   # webpack-dev-server with HMR at http://localhost:3000
```

### Build for production
```bash
npm run build  # emits to dist/
```

### Running Tests
```bash
npm test                       # Jest + RTL (unit / component)
npm test -- --watch            # watch mode
npm run test:e2e:frontend      # Playwright e2e
npm run test:e2e:frontend:ui   # Playwright UI runner
```

### Type-check & lint
```bash
npm run type-check  # tsc --noEmit
npm run lint        # eslint --fix
```

## 📂 Project Structure (template)
```
${PROJECT_NAME}/
├── .github/
│   ├── workflows/             # CI: build, lint, test, type-check (+ deploy-spa for Pages)
│   ├── CODEOWNERS
│   └── PULL_REQUEST_TEMPLATE.md
├── .husky/                    # pre-commit / pre-push hooks
├── .vscode/
├── public/
│   └── index.html             # ships <meta name="viewport"> — do not remove
├── src/
│   ├── capabilities/          # vertical slices: domain / application / infrastructure / ui
│   │   └── <feature>/
│   │       ├── domain/        # entities, dto, enums, ports — no I/O, no React
│   │       ├── application/   # use-cases, factories — depends on domain only
│   │       ├── infrastructure/# adapters implementing domain ports
│   │       ├── ui/            # components, pages, styles.module.css
│   │       ├── context.tsx    # composition root — wires infra → app → React tree
│   │       └── index.ts       # public barrel
│   ├── shared/
│   │   └── styles/            # design tokens + theme
│   ├── routes/                # app-level routing
│   ├── App.tsx
│   └── index.tsx
├── tests/
│   └── e2e/                   # Playwright specs
├── .babelrc
├── .gitignore
├── .prettierrc.js
├── .stylelintrc.json
├── eslint.config.js
├── jest.config.cjs
├── jest.setup.ts
├── lint-staged.config.js
├── package.json
├── playwright.config.ts
├── tsconfig.json
├── webpack.config.js
├── LICENSE
└── README.md
```

## 🚢 Deployment — GitHub Pages

The scaffold ships `.github/workflows/deploy-spa.yml`, which builds the SPA
with `PUBLIC_PATH=/<repo-name>/`, adds a `404.html` fallback for client-side
routes, and pushes `dist/` to `gh-pages` on every push to `main`.

**One-time setup is required** — GitHub no longer auto-enables Pages on
first `gh-pages` push. After the first successful workflow run, run:

```bash
gh api -X POST repos/${GITHUB_USERNAME}/${PROJECT_NAME}/pages \
  -f 'source[branch]=gh-pages' -f 'source[path]=/'
```

…or enable it manually via `Settings → Pages → Source: gh-pages → /`.

See `CLAUDE.md → Deployment` for the full rationale (token scopes, router
basename, custom domains).

## 👨‍💻 Authors
- ${GITHUB_USERNAME} — [GitHub](https://github.com/${GITHUB_USERNAME})

## 📜 License
This project is licensed under ${PROJECT_LICENSE}.

## 🙌 Acknowledgments
- Scaffolded with [BlueprintX](https://github.com/guilhermegor/blueprintx)'s `react-spa-webpack` skeleton.

## 🔗 Useful Links
- [GitHub Repository](https://github.com/${GITHUB_USERNAME}/${PROJECT_NAME})
- [Issue Tracker](https://github.com/${GITHUB_USERNAME}/${PROJECT_NAME}/issues)
