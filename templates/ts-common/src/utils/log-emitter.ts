/**
 * Injectable log sink and its two default implementations (blueprintx#436).
 *
 * A caller depends on this port, never on `console` directly — the port's
 * value is the swappable DESTINATION, not levels `console` already has (JS
 * levels/timestamps are already handled by the platform, unlike Python's
 * bare `print()`). `NULL_EMITTER` is the default for a published library,
 * which must not write to a host's output on its own initiative;
 * `CONSOLE_EMITTER` is the default for the browser SPA tier, where
 * `console` is the only destination reachable without an explicit network
 * call. See `ts-common/CLAUDE.md` for the full reasoning.
 */
export interface LogEmitter {
  debug(message: string, context?: Record<string, unknown>): void;
  info(message: string, context?: Record<string, unknown>): void;
  warn(message: string, context?: Record<string, unknown>): void;
  error(message: string, context?: Record<string, unknown>): void;
}

/**
 * No-op `LogEmitter` — the `ts-lib` default.
 *
 * A published package cannot know whether its host wants pino, winston, a
 * browser collector, or silence, so it must not call `console` (or anything
 * else) on its own initiative. The host injects whichever emitter it wants;
 * a library that never receives one gets this.
 */
export const NULL_EMITTER: LogEmitter = {
  debug: () => {},
  info: () => {},
  warn: () => {},
  error: () => {},
};

/**
 * `LogEmitter` that delegates to `console.*` — the `react-spa-webpack` default.
 *
 * In a browser, `console` is the only destination reachable without an
 * explicit `fetch()`/`sendBeacon()` call (no filesystem, no implicit
 * network). Swapping the destination later (e.g. an OTLP exporter, tracked
 * separately in blueprintx#438) means constructing a different `LogEmitter`
 * at the composition root — call sites never change.
 */
export const CONSOLE_EMITTER: LogEmitter = {
  debug: (message, context) =>
    context ? console.debug(message, context) : console.debug(message),
  info: (message, context) => (context ? console.info(message, context) : console.info(message)),
  warn: (message, context) => (context ? console.warn(message, context) : console.warn(message)),
  error: (message, context) =>
    context ? console.error(message, context) : console.error(message),
};
