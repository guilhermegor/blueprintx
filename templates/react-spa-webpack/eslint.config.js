import js from '@eslint/js';
import prettierConfig from 'eslint-config-prettier';
import boundaries from 'eslint-plugin-boundaries';
import importPlugin from 'eslint-plugin-import';
import jest from 'eslint-plugin-jest';
import jsxA11y from 'eslint-plugin-jsx-a11y';
import react from 'eslint-plugin-react';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import globals from 'globals';
import tseslint from 'typescript-eslint';

export default [
  {
    ignores: [
      '**/dist/**',
      '**/node_modules/**',
      '**/build/**',
      '**/coverage/**',
      '**/*.config.js',
      '**/*.config.cjs',
      '**/*.rtk.ts',
      '**/*.rtk.tsx',
      '**/*.zustand.ts',
      '**/*.zustand.tsx',
    ],
  },

  js.configs.recommended,
  ...tseslint.configs.recommended,

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

  {
    files: ['**/*.{test,spec}.{ts,tsx,js,jsx}'],
    plugins: { jest },
    rules: {
      'no-console': 'off',
      'jest/no-export': 'error',
    },
  },

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
      '@typescript-eslint/no-magic-numbers': [
        'error',
        {
          detectObjects: true,
          ignoreArrayIndexes: true,
          ignoreEnums: true,
          ignoreNumericLiteralTypes: true,
          ignoreReadonlyClassProperties: true,
          ignore: [-1, 0, 1, 2],
        },
      ],
      complexity: ['error', 3],
      '@typescript-eslint/use-unknown-in-catch-callback-variable': 'error',
      '@typescript-eslint/only-throw-error': 'error',
    },
  },

  {
    files: ['**/*.{test,spec}.{ts,tsx,js,jsx}'],
    rules: {
      complexity: ['error', 2],
    },
  },

  {
    files: ['src/**/*.ts'],
    rules: {
      'max-lines-per-function': [
        'error',
        { max: 60, skipBlankLines: false, skipComments: true, IIFEs: true },
      ],
    },
  },

  {
    files: ['src/**/*.{tsx,jsx}'],
    rules: {
      'max-lines-per-function': [
        'error',
        { max: 100, skipBlankLines: false, skipComments: true, IIFEs: true },
      ],
    },
  },

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
      'boundaries/dependencies': [
        'error',
        {
          default: 'disallow',
          policies: [
            ...[
              ['application', ['domain']],
              ['infrastructure', ['domain']],
              ['ui', ['application', 'domain', 'composition-root', 'shared']],
              ['composition-root', ['domain', 'application', 'infrastructure', 'shared']],
              ['barrel', ['domain', 'application', 'ui', 'composition-root']],
              ['shared', ['shared']],
              ['routes', ['barrel', 'shared']],
            ].map(([from, list_to]) => ({
              from: { element: { type: from } },
              allow: { to: { element: { types: { anyOf: list_to } } } },
            })),
          ],
        },
      ],
    },
  },

  {
    files: ['src/**/*-worker.js'],
    languageOptions: {
      globals: {
        ...globals.worker,
      },
    },
  },

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

  prettierConfig,
];
