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
npm install
npm run build       # emits dist/esm, dist/cjs, dist/types
npm test
npm run lint
npm run type-check
npm run pack:smoke  # npm pack -> install from the tarball -> require()/import() it
```

## Publishing

Packaged as dual ESM + CommonJS with bundled `.d.ts` declarations (see `exports`
in `package.json`). Releases publish via **npm OIDC trusted publishing** — no
long-lived `NPM_TOKEN` is stored. See `docs/contributing.md` for the release
workflow and the one-time bootstrap steps required before the first automated
publish.

## Documentation

A [Docusaurus](https://docusaurus.io) site lives in `docs/`, with native version
support (the npm-ecosystem analogue of `mike` on the Python skeletons):

```bash
npm run docs:start   # serve the docs site locally
npm run docs:build   # build the static site into docs-build/
```

## License

${PROJECT_LICENSE}
