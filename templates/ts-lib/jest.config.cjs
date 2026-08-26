/** @type {import('jest').Config} */
module.exports = {
  // A library has no DOM; jsdom (used by the react-spa-webpack skeleton) is
  // dead weight here — 'node' is Jest's built-in default environment.
  testEnvironment: 'node',
  testMatch: ['<rootDir>/src/**/*.{test,spec}.ts'],
  transform: {
    '^.+\\.ts$': 'babel-jest',
  },
  moduleFileExtensions: ['ts', 'js', 'json'],
};
