import js from '@eslint/js';
import prettierConfig from 'eslint-config-prettier';
import boundaries from 'eslint-plugin-boundaries';
import importPlugin from 'eslint-plugin-import';
import jsxA11y from 'eslint-plugin-jsx-a11y';
import react from 'eslint-plugin-react';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import globals from 'globals';
import tseslint from 'typescript-eslint';

export default [
  // 1. Global ignores
  {
    ignores: [
      '**/dist/**',
      '**/node_modules/**',
      '**/build/**',
      '**/coverage/**',
      '**/*.config.js',
      '**/*.config.cjs',
    ],
  },

  // 2. Base config for all source files
  js.configs.recommended,
  ...tseslint.configs.recommended,

  // 3. React-specific config
  {
    files: ['**/*.{jsx,tsx}'],
    plugins: {
      react,
      'react-hooks': reactHooks,
      'jsx-a11y': jsxA11y,
      'react-refresh': reactRefresh,
    },
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      globals: {
        ...globals.browser,
        ...globals.node,
      },
      parserOptions: {
        ecmaFeatures: { jsx: true },
      },
    },
    settings: {
      react: {
        version: 'detect',
      },
    },
    rules: {
      ...react.configs.recommended.rules,
      ...reactHooks.configs.recommended.rules,
      'react/react-in-jsx-scope': 'off',
      'react/prop-types': 'off',
      'jsx-a11y/alt-text': 'warn',
      'jsx-a11y/anchor-is-valid': 'warn',
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
    },
  },

  // 4. Overrides for test files
  {
    files: ['**/*.{test,spec}.{ts,tsx,js,jsx}'],
    rules: {
      'no-console': 'off',
    },
  },

  // 5. TypeScript type-aware linting
  {
    files: ['src/**/*.{ts,tsx}'],
    languageOptions: {
      parser: tseslint.parser,
      parserOptions: {
        project: './tsconfig.json',
        tsconfigRootDir: import.meta.dirname,
      },
    },
    rules: {
      ...tseslint.configs.recommendedTypeChecked[0].rules,
      '@typescript-eslint/no-floating-promises': 'error',
      '@typescript-eslint/no-misused-promises': 'error',
      '@typescript-eslint/no-unused-vars': [
        'warn',
        {
          argsIgnorePattern: '^_',
          varsIgnorePattern: '^_',
        },
      ],
      '@typescript-eslint/no-explicit-any': 'warn',
    },
  },

  // 6. DDD import boundary rules
  {
    plugins: { boundaries },
    settings: {
      'boundaries/elements': [
        { type: 'domain', pattern: 'capabilities/*/domain/**' },
        { type: 'application', pattern: 'capabilities/*/application/**' },
        { type: 'infrastructure', pattern: 'capabilities/*/infrastructure/**' },
        { type: 'ui', pattern: 'capabilities/*/ui/**' },
        { type: 'composition-root', pattern: 'capabilities/*/{context,*ContextProvider,use-*-context}*' },
        { type: 'barrel', pattern: 'capabilities/*/index.ts' },
        { type: 'shared', pattern: 'shared/**' },
        { type: 'routes', pattern: 'routes/**' },
      ],
      'boundaries/ignore': ['**/*.test.*', '**/*.spec.*'],
    },
    rules: {
      'boundaries/element-types': [
        'error',
        {
          default: 'disallow',
          rules: [
            // Classical hexagonal: domain has no deps; application depends only
            // on domain (ports). Infrastructure implements ports — also only
            // domain. composition-root is the DI assembly point.
            { from: ['domain'], allow: [] },
            { from: ['application'], allow: ['domain'] },
            { from: ['infrastructure'], allow: ['domain'] },
            { from: ['ui'], allow: ['application', 'domain', 'composition-root', 'shared'] },
            { from: ['composition-root'], allow: ['domain', 'application', 'infrastructure', 'shared'] },
            { from: ['barrel'], allow: ['domain', 'application', 'ui', 'composition-root'] },
            { from: ['shared'], allow: ['shared'] },
            { from: ['routes'], allow: ['barrel', 'shared'] },
          ],
        },
      ],
    },
  },

  // 7. Web worker files - use Worker globals, not DOM
  {
    files: ['src/**/*-worker.js'],
    languageOptions: {
      globals: {
        ...globals.worker,
      },
    },
  },

  // 8. Import resolution and ordering
  {
    files: ['src/**/*.{ts,tsx,js,jsx}'],
    plugins: { import: importPlugin },
    settings: {
      'import/resolver': {
        typescript: {
          alwaysTryTypes: true,
          project: './tsconfig.json',
        },
        node: {
          extensions: ['.js', '.jsx', '.ts', '.tsx', '.json', '.css'],
        },
      },
    },
    rules: {
      'import/no-unresolved': 'error',
      'import/no-duplicates': 'error',
      'import/no-cycle': ['error', { maxDepth: 10 }],
      'import/order': [
        'error',
        {
          groups: ['builtin', 'external', 'internal', 'parent', 'sibling', 'index'],
          'newlines-between': 'always',
          alphabetize: { order: 'asc', caseInsensitive: true },
        },
      ],
    },
  },

  // 9. Prettier config (must be last)
  prettierConfig,
];
