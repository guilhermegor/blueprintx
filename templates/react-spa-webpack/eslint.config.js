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
      // Keep in sync with tsconfig.json's `exclude`. The inactive
      // state-manager variants are excluded from the TS project, so the
      // type-aware parser cannot lint them — ignore them here too.
      '**/*.rtk.ts',
      '**/*.rtk.tsx',
      '**/*.zustand.ts',
      '**/*.zustand.tsx',
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
      // Cyclomatic-complexity ceiling, ESLint's built-in `complexity` rule —
      // mirrors templates/python-common's ruff C901 gate (#167), recalibrated
      // for this tree rather than copied by symmetry: measured against the
      // scaffolded example capability, 3 is the tightest ceiling with zero
      // current violations (2 already flags 4/25 functions, ~16%). See #168.
      complexity: ['error', 3],
      // Catch-safety, type-aware half of #440. `strict: true` (tsconfig.json)
      // already forces `useUnknownInCatchVariables`, so a `catch (err)`
      // clause's variable is `unknown` — but that compiler flag does NOT
      // reach a promise `.catch(cb)` callback, whose parameter stays `any`
      // even under strict mode. This rule closes that one remaining gap.
      '@typescript-eslint/use-unknown-in-catch-callback-variable': 'error',
      // Catch-safety (#440): only `Error` values may be thrown, so a
      // `catch`'s `instanceof Error` narrowing can actually succeed —
      // throwing a string/number/plain object would defeat every
      // downstream narrowing check silently. `no-empty` / `no-useless-catch`
      // already come from js.configs.recommended; this is the remaining gap.
      '@typescript-eslint/only-throw-error': 'error',
    },
  },

  // 6. Cyclomatic-complexity ceiling for test files — stricter than src/,
  // because a test with a branch tests two paths and the green run never
  // says which one. Placed after rule 5 so it wins for *.test.tsx files
  // that live under src/ (flat config: later entries win on shared keys).
  // Measured at 2: zero violations across colocated unit tests + Playwright
  // e2e specs; 1 was not payable yet (1/6 functions, ~17%). See #168.
  {
    files: ['**/*.{test,spec}.{ts,tsx,js,jsx}'],
    rules: {
      complexity: ['error', 2],
    },
  },

  // 7. Function-length ceiling for `.ts` — logic (#439). Mirrors
  // python-common's 60-line ceiling (`check_function_length.py`) — same
  // argument, a `.ts` file's body is logic, not markup. Measured with
  // `--rule '{"max-lines-per-function":["warn",{"max":0}]}'`
  // (blueprintx#425's technique, not read off docs): the longest function
  // in this scaffold is 27 lines (`useCreateNote`), so 60 costs zero
  // findings today — the same "prevents regression, not debt" profile as
  // the complexity gate above.
  //
  // Deliberately NOT the same options as Python's exclusion, and that gap
  // is accepted rather than compensated: `skipBlankLines: false` matches
  // Python (`node.end_lineno - node.lineno + 1` counts blank lines too),
  // but `skipComments: true` is the nearest ESLint has to "docstring
  // excluded" and is NOT equivalent — it skips every comment, including
  // inline ones, not only a leading doc block, so the same digit buys a
  // slightly more permissive rule here. Not compensated with a lower
  // number because every measured function sits 33+ lines under 60 either
  // way; an arbitrary correction would buy no real protection. `IIFEs:
  // true` because an IIFE is still a function body that can grow unchecked
  // — no reason to exempt the one shape that hides behind a call
  // expression. See rule 8 immediately below for the `.tsx` twin, which
  // shares this same options reasoning but not the same ceiling.
  {
    files: ['src/**/*.ts'],
    rules: {
      'max-lines-per-function': [
        'error',
        { max: 60, skipBlankLines: false, skipComments: true, IIFEs: true },
      ],
    },
  },

  // 8. Function-length ceiling for `.tsx`/`.jsx` — markup, not logic (#439,
  // owner decision: settled as its own block with its own number, never
  // merged into rule 7 even if the digits match some week). A component's
  // returned JSX can legitimately run long — conditional branches, mapped
  // lists — and policing it at a logic ceiling is a rule people turn off,
  // which reads as coverage while providing none.
  //
  // Measured the same way as rule 7: the longest `.tsx` function today is
  // 23 lines (`NoteProvider`). 100 is not that number scaled up by
  // convention — it is chosen to leave roughly 4x headroom over what this
  // template's own example capability needs, high enough that it only
  // fires once a component has clearly outgrown a single responsibility.
  {
    files: ['src/**/*.{tsx,jsx}'],
    rules: {
      'max-lines-per-function': [
        'error',
        { max: 100, skipBlankLines: false, skipComments: true, IIFEs: true },
      ],
    },
  },

  // 9. DDD import boundary rules
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

  // 10. Web worker files - use Worker globals, not DOM
  {
    files: ['src/**/*-worker.js'],
    languageOptions: {
      globals: {
        ...globals.worker,
      },
    },
  },

  // 11. Import resolution and ordering
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

  // 12. Prettier config (must be last)
  prettierConfig,
];
