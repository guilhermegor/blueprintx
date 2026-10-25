<!-- readme-archetype: library -->
# ${PROJECT_NAME}

[![Project Status: Active](https://www.repostatus.org/badges/latest/active.svg)](https://www.repostatus.org/#active)
![Node](https://img.shields.io/badge/node-%E2%89%A522-339933?logo=node.js&logoColor=white)
![TypeScript](https://img.shields.io/badge/typescript-6.x-3178C6?logo=typescript&logoColor=white)
[![Linting](https://img.shields.io/badge/linting-eslint_|_prettier-blue)](https://eslint.org)
![License](https://img.shields.io/badge/license-${PROJECT_LICENSE}-green.svg)
![Open Issues](https://img.shields.io/github/issues/${GITHUB_USERNAME}/${PROJECT_NAME})

<!-- slug: overview -->
## Overview

${PROJECT_DESCRIPTION}

<!-- slug: documentation -->
## Documentation

The documentation site lives at https://${GITHUB_USERNAME}.github.io/${PROJECT_NAME}/. Serve it locally with `npm run docs:start`.

<!-- slug: getting-started -->
## Getting Started

<!-- slug: install -->
### Install

```bash
npm install ${PROJECT_NAME}
```

<!-- slug: usage -->
### Usage

```ts
import { greet } from '${PROJECT_NAME}';

greet('World'); // "Hello, World!"
```

<!-- slug: project-structure -->
## Project Structure

```text
${PROJECT_NAME}/
├── src/          library source; src/index.ts is the public entry point
├── tests/        Jest suites
├── docs/         Docusaurus site
├── .specs/       feature specs and backlog trackers
└── package.json  exports map for ESM, CJS and .d.ts
```

Feature specs live under `.specs/features/`; `.specs/CLAUDE.md` holds the layout rules and
the template with its `US-`/`AC-`/`ASM-`/`Q-XXX` id conventions.

A [Docusaurus](https://docusaurus.io) site lives in `docs/`, with native version support
(the npm-ecosystem analogue of `mike` on the Python skeletons):

```bash
npm run docs:start   # serve the docs site locally
npm run docs:build   # build the static site into docs-build/
```

<!-- slug: development -->
## Development

```bash
npm install
npm run build       # emits dist/esm, dist/cjs, dist/types
npm test
npm run lint
npm run type-check
npm run pack:smoke  # npm pack -> install from the tarball -> require()/import() it
```

<!-- slug: public-api -->
## Public API

Only what `src/index.ts` re-exports is part of the published surface — everything
else under `src/` is an implementation detail and may change without notice.

<!-- slug: publishing -->
## Publishing

Packaged as dual ESM + CommonJS with bundled `.d.ts` declarations (see `exports`
in `package.json`). Releases publish via **npm OIDC trusted publishing** — no
long-lived `NPM_TOKEN` is stored. See `docs/contributing.md` for the release
workflow and the one-time bootstrap steps required before the first automated
publish.

<!-- slug: contributing -->
## Contributing

See `docs/contributing.md` for the branch, commit and release rules.

<!-- slug: license -->
## License

${PROJECT_LICENSE}; see [LICENSE](LICENSE).

<!-- slug: authors -->
## Authors

- ${AUTHOR_NAME} — [GitHub](https://github.com/${GITHUB_USERNAME}) | [LinkedIn](${LINKEDIN_URL})

<!-- slug: useful-links -->
## Useful Links

- [GitHub Repository](https://github.com/${GITHUB_USERNAME}/${PROJECT_NAME})
- [Issue Tracker](https://github.com/${GITHUB_USERNAME}/${PROJECT_NAME}/issues)
