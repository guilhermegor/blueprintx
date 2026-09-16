/** @type {import('jest').Config} */
module.exports = {
  // Shuffles test order per run so a hidden order dependency fails instead of passing
  // silently forever (blueprintx#442). Jest reports the seed on every run, pass or fail;
  // reproduce that order by passing it back as `jest --seed=<N>` — it reports the number,
  // not a ready-made command. See CONTRIBUTING.md: a seed-specific failure is a real
  // defect, never flakiness to re-run away.
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
