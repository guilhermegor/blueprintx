import js from '@eslint/js';
import eslintReact from '@eslint-react/eslint-plugin';
import prettierConfig from 'eslint-config-prettier';
import boundaries from 'eslint-plugin-boundaries';
import { createTypeScriptImportResolver } from 'eslint-import-resolver-typescript';
import importPlugin from 'eslint-plugin-import-x';
import jest from 'eslint-plugin-jest';
import jsxA11y from 'eslint-plugin-jsx-a11y';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import globals from 'globals';
import tseslint from 'typescript-eslint';

const skipIssue = {
  rules: {
    'require-issue': {
      meta: {
        type: 'problem',
        schema: [],
        messages: { missing: 'A disabled or focused test rule needs an issue reference, e.g. `-- #123`.' },
      },
      create: (context) => ({
        Program: () => {
          context.sourceCode
            .getAllComments()
            .map((c) => [c, /^\s*eslint-disable(?:-next-line|-line)?(?:\s([\s\S]*))?$/.exec(c.value)])
            .filter(([c, m]) => m
              ? /^$|jest\/no-(?:disabled|focused)-tests/.test(
                (m[1] ?? '').split(/(?:^|\s)-{2,}(?:\s|$)/)[0].trim())
              : /^\s*eslint\s[^]*jest\/no-(?:disabled|focused)-tests/.test(c.value))
            .map(([c]) => c)
            .filter((c) => !/#\d+/.test(c.value))
            .forEach((c) => context.report({ loc: c.loc, messageId: 'missing' }));
        },
      }),
    },
  },
};

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
    files: ['**/*.cjs'],
    languageOptions: {
      sourceType: 'commonjs',
      globals: globals.node,
    },
    rules: {
      '@typescript-eslint/no-require-imports': 'off',
    },
  },

  { files: ['**/*.{jsx,tsx}'], ...eslintReact.configs['recommended-typescript'] },

  {
    files: ['**/*.{jsx,tsx}'],
    plugins: {
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
    rules: {
      ...reactHooks.configs.recommended.rules,
      'jsx-a11y/alt-text': 'warn',
      'jsx-a11y/anchor-is-valid': 'warn',
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
    },
  },

  {
    files: ['**/*.{test,spec}.{ts,tsx,js,jsx}'],
    plugins: { jest, skip: skipIssue },
    rules: {
      'no-console': 'off',
      'skip/require-issue': 'error',
      'jest/no-export': 'error',
      'jest/no-disabled-tests': 'error',
      'jest/no-focused-tests': 'error',
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
      '@typescript-eslint/no-explicit-any': 'error',
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
        { type: 'shared', pattern: 'shared/**' },
        { type: 'routes', pattern: 'routes/**' },
      ],
      'boundaries/files': [{ category: 'barrel', pattern: 'capabilities/*/index.ts' }],
      'boundaries/ignore': ['**/*.test.*', '**/*.spec.*'],
      'import/resolver': {
        typescript: { alwaysTryTypes: true, project: './tsconfig.json' },
      },
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
              ['shared', ['shared']],
            ].map(([from, list_to]) => ({
              from: { element: { type: from } },
              allow: { to: { element: { types: { anyOf: list_to } } } },
            })),
            {
              from: { file: { categories: 'barrel' } },
              allow: {
                to: {
                  element: { types: { anyOf: ['domain', 'application', 'ui', 'composition-root'] } },
                },
              },
            },
            {
              from: { element: { type: 'routes' } },
              allow: [
                { to: { file: { categories: 'barrel' } } },
                { to: { element: { type: 'shared' } } },
              ],
            },
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
    plugins: { 'import-x': importPlugin },
    settings: {
      'import-x/resolver-next': [
        createTypeScriptImportResolver({ alwaysTryTypes: true, project: './tsconfig.json' }),
      ],
    },
    rules: {
      'import-x/no-unresolved': 'error',
      'import-x/no-duplicates': 'error',
      'import-x/no-cycle': ['error', { maxDepth: 10 }],
      'import-x/order': [
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
