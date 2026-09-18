const path = require('node:path');

/** @type {import('jest').Config} */
module.exports = {
  // Shuffles test order per run so a hidden order dependency fails instead of passing
  // silently forever (blueprintx#442). Jest reports the seed on every run, pass or fail;
  // reproduce that order by passing it back as `jest --seed=<N>` — it reports the number,
  // not a ready-made command. See docs/contributing.md: a seed-specific failure is a real
  // defect, never flakiness to re-run away.
  randomize: true,
  // A library has no DOM; jsdom (used by the react-spa-webpack skeleton) is
  // dead weight here — 'node' is Jest's built-in default environment.
  testEnvironment: 'node',
  testMatch: ['<rootDir>/src/**/*.{test,spec}.ts'],
  transform: {
    // Explicit, absolute configFile (babel-jest does not expand Jest's own <rootDir>
    // token inside a transform option): a plain `.babelrc` at the project root would
    // also be picked up by Docusaurus's own webpack/babel-loader when building docs/,
    // breaking its build. See babel.config.test.cjs's header comment.
    '^.+\\.ts$': [
      'babel-jest',
      { configFile: path.join(__dirname, 'babel.config.test.cjs') },
    ],
  },
  moduleFileExtensions: ['ts', 'js', 'json'],
};
