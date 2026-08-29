/**
 * Public API barrel. Only what is re-exported here is part of the package's
 * public surface (and therefore covered by dist/types/index.d.ts).
 */
// The .js extension (not .ts) is required so the compiled ESM output resolves the
// sibling module at runtime — Node's native ESM resolver, unlike CJS or Jest, does not
// guess extensions. tsc maps it back to ./example.ts for type-checking.
export { greet } from './example.js';
