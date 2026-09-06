import path from 'node:path';
import { builtinModules } from 'node:module';

import js from '@eslint/js';
import prettierConfig from 'eslint-config-prettier';
import importPlugin from 'eslint-plugin-import';
import tseslint from 'typescript-eslint';

// Deny-by-default vendor allowlist, per layer, each entry carrying a WRITTEN REASON —
// the TS mirror of the Python skeletons' `.layer-policy.yaml` + `check_layer_imports.py`
// (blueprintx#345). A third-party import passes only if the file's layer lists it here;
// `no-restricted-imports` was rejected because it is a BLOCKLIST — the inverse polarity —
// and by construction cannot catch a vendor nobody thought to list.
//
// ⚠️ Lives INLINE here rather than in the shared `templates/ts-common/` tree. The Python
// precedent is for the ENGINE to be shared — the per-tier POLICY itself already follows
// the Python precedent, since `.layer-policy.yaml` is per-tier there too (the allowed
// vendors genuinely differ by project). Reaching a generated ts-lib project with a NEW
// file requires a `cp` line in `bin/scaffold/ts_lib.sh`, out of scope for this change
// (blueprintx#345 forbids editing `bin/**` here). `eslint.config.mjs` is already copied
// verbatim by the existing scaffold, so the policy travels with it for free. Should a
// shared engine become worth it later (e.g. react-spa-webpack adopts this mechanism too),
// extracting this rule into `templates/ts-common/` is a mechanical follow-up, not a rewrite.
//
// ⚠️ No `boundaries` (layer-DIRECTION) entry here, unlike react-spa-webpack's
// eslint.config.js — ts-lib is a FLAT library (`src/index.ts` barrel + siblings), so there
// is no internal layer to police direction between. `boundaries` polices layers that
// exist; adding it here would police nothing.
const VENDOR_POLICY = {
  // No sub-directory carries different rules today — ts-lib ships src/index.ts + siblings
  // with nothing nested under it. One key covers the whole tree; add a second the day this
  // skeleton grows a real subdirectory that should carry a different vendor set.
  __root__: {
    allow: {
      // vendorName: 'the written reason it is needed in this layer',
    },
  },
};

/** Reject a bare allowlist entry AT CONFIG-LOAD TIME, not silently. */
function validateVendorPolicy(policy) {
  for (const [layer, { allow = {} }] of Object.entries(policy)) {
    for (const [vendor, reason] of Object.entries(allow)) {
      if (typeof reason !== 'string' || reason.trim() === '') {
        throw new Error(
          `eslint.config.mjs: VENDOR_POLICY.${layer}.allow['${vendor}'] has no written ` +
            `reason. An allowlist entry without one is a rule that the first person who ` +
            `finds it inconvenient will widen.`
        );
      }
    }
  }
}
validateVendorPolicy(VENDOR_POLICY);

/** The layer a file belongs to: its first path component under src/, or '__root__'. */
function layerFor(filename) {
  const relative = path.relative(path.join(process.cwd(), 'src'), filename);
  const [first] = relative.split(path.sep);
  return first && !first.endsWith('.ts') ? first : '__root__';
}

/** Root package name of an import specifier, or null when it needs no policy entry. */
function vendorRoot(specifier) {
  if (specifier.startsWith('.') || specifier.startsWith('/')) return null; // first-party
  if (specifier.startsWith('node:')) return null; // stdlib, explicit form
  const parts = specifier.split('/');
  const root = specifier.startsWith('@') ? parts.slice(0, 2).join('/') : parts[0];
  return builtinModules.includes(root) ? null : root; // stdlib, bare form (e.g. 'fs')
}

// A local ESLint rule (no new dependency — ESLint's flat config natively supports an
// inline plugin+rule object). Scope is deliberately irrelevant to the verdict, exactly
// like the Python gate: a dynamic `import('vendor')` is judged the same as a top-level one.
/** Whether an import carries NO runtime coupling — type-only at the declaration or on every
 *  specifier. A bare `import 'p'` has no specifiers and IS a runtime side-effect import, so it
 *  must not qualify: `.every()` on an empty array returns true, hence the length guard. */
function isTypeOnlyImport(node) {
	if (node.importKind === 'type') return true;
	const list_specs = node.specifiers ?? [];
	return list_specs.length > 0 && list_specs.every((s) => s.importKind === 'type');
}

/** The export-side twin of isTypeOnlyImport. `export * from 'p'` has no specifiers and re-exports
 *  runtime bindings, so the same length guard applies. */
function isTypeOnlyExport(node) {
	if (node.exportKind === 'type') return true;
	const list_specs = node.specifiers ?? [];
	return list_specs.length > 0 && list_specs.every((s) => s.exportKind === 'type');
}

/** Whether a dynamic-import specifier is provably first-party: a template literal whose FIXED
 *  leading text is relative. `` `./x/${y}` `` cannot reach a package whatever `y` holds; a
 *  template starting with an interpolation (`` `${p}/x` ``) proves nothing and is not exempt. */
function isProvablyLocalSpecifier(node) {
	if (node.type !== 'TemplateLiteral' || node.quasis.length === 0) return false;
	const str_head = node.quasis[0].value.cooked ?? '';
	return str_head.startsWith('./') || str_head.startsWith('../');
}

const vendorAllowlistRule = {
  meta: {
    type: 'problem',
    docs: { description: 'deny-by-default vendor allowlist per layer, with a written reason' },
  },
  create(context) {
    const layer = layerFor(context.filename);
    const allow = VENDOR_POLICY[layer]?.allow ?? {};
    function check(node, specifier) {
      const root = vendorRoot(specifier);
      if (root === null || Object.hasOwn(allow, root)) return;
      context.report({
        node,
        message:
          `'${root}' is not allowed in layer '${layer}'. Add it to VENDOR_POLICY.${layer}` +
          `.allow in eslint.config.mjs with a written reason, or import it through a ` +
          `relative module.`,
      });
    }
    return {
      // ⚠️ TWO PLACES CARRY `type`, AND CHECKING ONLY THE OUTER ONE IS INCONSISTENT.
      //
      // `import type { A } from 'p'` sets importKind='type' on the DECLARATION.
      // `import { type A } from 'p'` leaves the declaration at 'value' and marks each
      // SPECIFIER instead. Both are erased at compile time, so both are equally free of
      // runtime coupling — but reading only the declaration passed the first and blocked the
      // second. Measured on blueprintx#348: `import type {Foo}` -> 0 findings,
      // `import {type Foo}` -> 1. Same semantics, opposite verdicts.
      //
      // A mixed import (`{ type Foo, merge }`) still couples: `merge` survives to runtime, so
      // it must fail — hence "every specifier is type", never "any".
      ImportDeclaration(node) {
        if (isTypeOnlyImport(node)) return; // erased at compile time, no runtime coupling
        check(node, node.source.value);
      },
      ExportNamedDeclaration(node) {
        if (!node.source || isTypeOnlyExport(node)) return;
        check(node, node.source.value);
      },
      ExportAllDeclaration(node) {
        if (node.exportKind === 'type' || !node.source) return;
        check(node, node.source.value);
      },
      // ⚠️ A NON-LITERAL `import(x)` USED TO EXIT SILENTLY, WHICH IS THE ONE OUTCOME A
      // DENY-BY-DEFAULT RULE MAY NEVER HAVE. The guard read "if I can resolve it, check it",
      // so `const v = 'lodash'; import(v)` reached any vendor with nothing asking — measured
      // on blueprintx#348: 0 findings. Unresolvable is not the same as allowed; a policy that
      // cannot see a specifier must SAY so, not wave it through.
      //
      // A relative specifier is exempt because it is provably first-party: `import('./x')` and
      // a template starting `./` or `../` cannot reach a package however the rest is built.
      ImportExpression(node) {
        const cls_src = node.source;
        if (cls_src.type === 'Literal' && typeof cls_src.value === 'string') {
          check(node, cls_src.value);
          return;
        }
        if (isProvablyLocalSpecifier(cls_src)) return;
        context.report({
          node,
          message:
            'dynamic import() with a non-literal specifier cannot be checked against ' +
            'VENDOR_POLICY. Use a string literal, or a template starting "./" or "../" for a ' +
            'local module — an unresolvable specifier is not an allowed one.',
        });
      },
      // ⚠️ `import x = require('pkg')` is a FIFTH way in, and it is the one a deny-by-default
      // list cannot afford to miss: the other four are ESM syntax a reader recognises as an
      // import, while this one reads like an assignment. typescript-eslint models it as
      // TSImportEqualsDeclaration whose `moduleReference` is a TSExternalModuleReference —
      // NOT a CallExpression, so nothing else in this visitor set sees it. Raised by review
      // on blueprintx#348.
      TSImportEqualsDeclaration(node) {
        if (node.importKind === 'type') return; // erased at compile time, like the ESM cases
        const cls_ref = node.moduleReference;
        if (
          cls_ref.type === 'TSExternalModuleReference' &&
          cls_ref.expression.type === 'Literal' &&
          typeof cls_ref.expression.value === 'string'
        ) {
          check(node, cls_ref.expression.value);
        }
      },
    };
  },
};

export default [
  // 1. Global ignores
  {
    ignores: [
      '**/dist/**',
      '**/node_modules/**',
      '**/coverage/**',
      '**/*.config.js',
      '**/*.config.cjs',
      '**/*.config.mjs',
      // Docusaurus tooling config, not library source — same reason *.config.js is ignored.
      'sidebars.js',
      // Jest-only Babel config; deliberately not named *.config.cjs (see its own header).
      'babel.config.test.cjs',
    ],
  },

  // 2. Base config for all source files
  js.configs.recommended,
  ...tseslint.configs.recommended,

  // 3. Overrides for test files
  {
    files: ['**/*.{test,spec}.ts'],
    rules: {
      'no-console': 'off',
    },
  },

  // 4. TypeScript type-aware linting
  {
    files: ['src/**/*.ts'],
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

  // 5. Function-length ceiling (#439). Mirrors python-common's 60-line
  // ceiling (`check_function_length.py`) — this skeleton is a flat library
  // with no `.tsx`/JSX (see the header comment above `VENDOR_POLICY`), so
  // there is no markup/logic split to make here: one block, one number.
  // Measured with `--rule '{"max-lines-per-function":["warn",{"max":0}]}'`
  // (blueprintx#425's technique): the longest function in this scaffold is
  // 5 lines, so 60 costs zero findings today.
  //
  // `skipBlankLines: false` matches Python (`node.end_lineno - node.lineno
  // + 1` counts blank lines too). `skipComments: true` is the nearest
  // ESLint has to "docstring excluded" and is NOT equivalent — it skips
  // every comment, including inline ones — accepted rather than
  // compensated, since every measured function sits 55+ lines under the
  // ceiling either way. `IIFEs: true` because an IIFE is still a function
  // body that can grow unchecked.
  {
    files: ['src/**/*.ts'],
    rules: {
      'max-lines-per-function': [
        'error',
        { max: 60, skipBlankLines: false, skipComments: true, IIFEs: true },
      ],
    },
  },

  // 6. Import resolution and ordering
  {
    files: ['src/**/*.ts'],
    plugins: { import: importPlugin },
    settings: {
      'import/resolver': {
        typescript: {
          alwaysTryTypes: true,
          project: './tsconfig.json',
        },
        node: {
          extensions: ['.js', '.ts', '.json'],
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

  // 7. Vendor allowlist (blueprintx#345) — deny-by-default, per layer, written reason required
  {
    files: ['src/**/*.ts'],
    ignores: ['**/*.{test,spec}.ts'],
    plugins: { local: { rules: { 'vendor-allowlist': vendorAllowlistRule } } },
    rules: { 'local/vendor-allowlist': 'error' },
  },

  // 8. Prettier config (must be last)
  prettierConfig,
];
