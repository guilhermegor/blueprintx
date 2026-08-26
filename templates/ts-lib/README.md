# ${PROJECT_NAME}

[![Project Status: Active](https://www.repostatus.org/badges/latest/active.svg)](https://www.repostatus.org/#active)
![Node](https://img.shields.io/badge/node-%E2%89%A522-339933?logo=node.js&logoColor=white)
![TypeScript](https://img.shields.io/badge/typescript-6.x-3178C6?logo=typescript&logoColor=white)
[![Linting](https://img.shields.io/badge/linting-eslint_|_prettier-blue)](https://eslint.org)
![License](https://img.shields.io/badge/license-${PROJECT_LICENSE}-green.svg)
![Open Issues](https://img.shields.io/github/issues/${GITHUB_USERNAME}/${PROJECT_NAME})

${PROJECT_DESCRIPTION}

## Install

```bash
npm install ${PROJECT_NAME}
```

## Usage

```ts
import { greet } from '${PROJECT_NAME}';

greet('World'); // "Hello, World!"
```

## Public API

Only what `src/index.ts` re-exports is part of the published surface — everything
else under `src/` is an implementation detail and may change without notice.

## Development

```bash
npm ci
npm run build       # emits dist/esm, dist/cjs, dist/types
npm test
npm run lint
npm run type-check
npm run pack:smoke  # npm pack -> install from the tarball -> require()/import() it
```

## Publishing

Packaged as dual ESM + CommonJS with bundled `.d.ts` declarations (see `exports`
in `package.json`). No npm publish workflow ships yet — that lands in a follow-up
slice (OIDC trusted publishing).

## License

${PROJECT_LICENSE}
