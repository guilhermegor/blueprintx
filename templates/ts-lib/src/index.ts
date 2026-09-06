/**
 * Public API barrel. Only what is re-exported here is part of the package's
 * public surface (and therefore covered by dist/types/index.d.ts).
 */
// The .js extension (not .ts) is required so the compiled ESM output resolves the
// sibling module at runtime — Node's native ESM resolver, unlike CJS or Jest, does not
// guess extensions. tsc maps it back to ./example.ts for type-checking.
export { greet } from './example.js';

// Shared logging port (blueprintx#436) — a published package must not log on its own
// initiative, so it defaults consumers to NULL_EMITTER; the host injects CONSOLE_EMITTER
// or its own LogEmitter implementation. Ships from templates/ts-common/src/utils/log-emitter.ts.
export type { LogEmitter } from './utils/log-emitter.js';
export { NULL_EMITTER, CONSOLE_EMITTER } from './utils/log-emitter.js';
