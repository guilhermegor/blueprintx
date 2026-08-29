const path = require('node:path');

/** @type {import('jest').Config} */
module.exports = {
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
