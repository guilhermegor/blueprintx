# Usage

Installing and importing this library.

## Installation

```bash
npm install ${PROJECT_NAME}
```

## Basic usage

```ts
import { greet } from '${PROJECT_NAME}';

greet('World'); // "Hello, World!"
```

Only what `src/index.ts` re-exports is part of the published surface — everything else
under `src/` is an implementation detail and may change without notice.

## Module formats

The package ships both ESM and CommonJS builds plus bundled `.d.ts` declarations, so
either import style resolves correctly:

```ts
// ESM
import { greet } from '${PROJECT_NAME}';
```

```js
// CommonJS
const { greet } = require('${PROJECT_NAME}');
```

## Running tests and lint locally

```bash
npm ci
npm run build       # emits dist/esm, dist/cjs, dist/types
npm test
npm run lint
npm run type-check
npm run pack:smoke   # npm pack -> install from the tarball -> require()/import() it
```
