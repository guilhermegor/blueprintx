/** @type {import('jest').Config} */
module.exports = {
  // Shuffles test order per run so a hidden order dependency fails instead of passing
  // silently forever (blueprintx#442). Jest prints the seed on every run, pass or fail, and
  // a failing run also prints the exact re-run command (`--seed=<N>`) — see CONTRIBUTING.md:
  // a seed-specific failure is a real defect, never flakiness to re-run away.
  randomize: true,
  testEnvironment: 'jsdom',
  testMatch: ['<rootDir>/src/**/*.{test,spec}.{ts,tsx}'],
  setupFilesAfterEnv: ['<rootDir>/jest.setup.ts'],
  moduleNameMapper: {
    '\\.module\\.css$': 'identity-obj-proxy',
    '\\.(css|less|scss|sass)$': 'identity-obj-proxy',
    '^@/(.*)$': '<rootDir>/src/$1',
  },
  transform: {
    '^.+\\.(ts|tsx|js|jsx)$': 'babel-jest',
  },
  moduleFileExtensions: ['ts', 'tsx', 'js', 'jsx', 'json'],
};
