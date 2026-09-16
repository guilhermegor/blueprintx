/**
 * OTLP log export (opt-in) — wraps a `LogEmitter` with an OpenTelemetry-backed exporter.
 *
 * ADDS OTLP export to whatever `LogEmitter` the caller already uses (`CONSOLE_EMITTER` in
 * react-spa-webpack, `NULL_EMITTER` in ts-lib, or a host's own implementation) — never in
 * place of it: a project with no collector configured keeps working exactly as before. This
 * is the only module that imports `@opentelemetry/*` (dynamically — see below), mirroring
 * `python-common/optional/otel_logging.py` (blueprintx#438) and the vendor-boundary reasoning
 * documented there.
 *
 * ⚠️ MEASURED (2026-09), not assumed: `@opentelemetry/api-logs`, `@opentelemetry/sdk-logs` and
 * `@opentelemetry/exporter-logs-otlp-http` are all published at 0.222.0 — the same "not yet
 * stable" status the Python Logs signal carries (see `otel_logging.py`'s module docstring for
 * that measurement). Pin exact versions in `package.json`; re-measure before bumping.
 *
 * ⚠️ SECOND measurement, specific to this runtime split: unlike Node's `OTLPLogExporter`
 * (which reads `OTEL_EXPORTER_OTLP_*` env vars itself, same as the Python SDK), the BROWSER
 * build takes NO env-var fallback at all (`@opentelemetry/otlp-exporter-base`'s
 * `convertLegacyBrowserHttpOptions` passes "no fallback for browser case") — a real browser
 * has no `process.env`. So this file resolves the endpoint and headers itself
 * (`resolveSignalOverride`, mirroring the Python port's precedence) and passes them EXPLICITLY
 * to the exporter, rather than leaving the SDK to read them — the opposite of what
 * `otel_logging.py` does, and deliberately so: relying on the SDK's own read would silently do
 * nothing in the browser. `process.env.<KEY>` is written as a literal member access (never a
 * computed lookup) because that is the exact shape react-spa-webpack's `webpack.config.js`
 * already replaces at build time via `DefinePlugin`, one entry per `.env` key — ts-lib reads
 * the same literal from the real `process.env` at runtime. One resolution path, both runtimes.
 *
 * ⚠️ THIRD, a known ceiling (ponytail): `otel_logging.py` hardens its `requests` session
 * against a credential-forwarding redirect (CWE-319, `max_redirects = 0`). This module cannot
 * do the equivalent for the BROWSER transport — it sends via `fetch`, which follows redirects
 * by default, and the exporter exposes no option to disable that. Node's own transport
 * (`http`/`https` core modules) does not auto-follow redirects, so the gap is browser-only.
 * The cleartext-credentials guard below (`isCleartextWithCredentials`) is the primary defence
 * in both runtimes; re-check the browser transport for a `redirect: 'error'` knob before
 * relying on this seam to carry a real credential across an origin that might redirect.
 */
import type { LogEmitter } from './log-emitter';

// A cleartext endpoint is only a credential leak when there is a credential to leak, and only
// when it leaves the machine — mirrors `_TUPLE_LOOPBACK_HOSTS` in otel_logging.py. The
// bracketed form is what the WHATWG URL API returns for an IPv6 literal's `.hostname`.
const LOOPBACK_HOSTS = new Set(['localhost', '127.0.0.1', '::1', '[::1]']);

// OTel Logs Data Model severity numbers (fixed by the spec, not reimplemented arbitrarily) —
// see @opentelemetry/api-logs's `SeverityNumber` enum, whose values these mirror. Hardcoded
// rather than importing the enum so the four numbers are available before the dynamic
// `import()` below resolves (or even when it never does — see the fire-and-forget note).
const OTEL_SEVERITY_NUMBER = { debug: 5, info: 9, warn: 13, error: 17 } as const;

/**
 * Resolve a signal-specific OTLP env value over its generic fallback.
 *
 * Presence decides, never truthiness — mirrors the Python port's `_signal_override`. A
 * signal-specific value that is SET BUT EMPTY still wins: the OTLP spec's precedence keys on
 * presence, so an `??`/`||` chain that treats `''` as "unset" would silently fall through to
 * the generic value and vet an endpoint the exporter is not using.
 *
 * @param signalValue - `process.env.OTEL_EXPORTER_OTLP_LOGS_<X>`, read at the call site (see
 *   the module docstring for why it must be a literal member access, not passed as a name).
 * @param genericValue - `process.env.OTEL_EXPORTER_OTLP_<X>`, the fallback.
 * @returns The effective value, trimmed; `''` when neither is set.
 */
export function resolveSignalOverride(
  signalValue: string | undefined,
  genericValue: string | undefined,
): string {
  if (signalValue !== undefined) {
    return signalValue.trim();
  }
  return (genericValue ?? '').trim();
}

/**
 * Report whether credentials would be sent over an unencrypted, off-host connection.
 *
 * @param endpoint - The effective OTLP logs endpoint.
 * @param hasHeaders - Whether `OTEL_EXPORTER_OTLP_[LOGS_]HEADERS` carries anything.
 * @returns `true` when the exporter must not be started.
 */
export function isCleartextWithCredentials(endpoint: string, hasHeaders: boolean): boolean {
  if (!hasHeaders || !endpoint) {
    return false;
  }
  let hostname: string;
  try {
    hostname = new URL(endpoint).hostname;
  } catch {
    // Unparseable endpoint + credentials: refuse. Mirrors otel_logging.py's
    // `_is_cleartext_with_credentials`, which takes the same should-fail direction.
    return true;
  }
  return !endpoint.startsWith('https://') && !LOOPBACK_HOSTS.has(hostname);
}

/** Parse `OTEL_EXPORTER_OTLP_[LOGS_]HEADERS`'s `key=value,key2=value2` format. */
function parseOtlpHeaders(raw: string): Record<string, string> {
  const headers: Record<string, string> = {};
  for (const pair of raw ? raw.split(',') : []) {
    const eq = pair.indexOf('=');
    if (eq === -1) continue;
    const key = pair.slice(0, eq).trim();
    if (key) headers[key] = pair.slice(eq + 1).trim();
  }
  return headers;
}

interface OtelLoggerLike {
  emit(record: {
    severityText: string;
    severityNumber: number;
    body: string;
    attributes?: Record<string, unknown>;
  }): void;
}

/**
 * Build the OTel logger provider and return a minimal emit-capable logger.
 *
 * Split out of `withOtelLogExport` so the dynamic import — the one place this package touches
 * `@opentelemetry/*` — is a single, separately awaitable async function, never inlined into
 * the fire-and-forget wrapper below.
 */
async function installOtelLogger(
  endpoint: string,
  headers: Record<string, string>,
): Promise<OtelLoggerLike> {
  const [{ logs }, { LoggerProvider, BatchLogRecordProcessor }, { OTLPLogExporter }, { detectResources, envDetector }] =
    await Promise.all([
      import('@opentelemetry/api-logs'),
      import('@opentelemetry/sdk-logs'),
      import('@opentelemetry/exporter-logs-otlp-http'),
      import('@opentelemetry/resources'),
    ]);

  const exporter = new OTLPLogExporter({ url: endpoint, headers });
  const provider = new LoggerProvider({
    // envDetector reads OTEL_SERVICE_NAME / OTEL_RESOURCE_ATTRIBUTES itself (measured against
    // its source) — the same env vars Python's bare `Resource.create()` reads, so this is the
    // JS equivalent, not a reimplementation of that lookup.
    resource: detectResources({ detectors: [envDetector] }),
    processors: [new BatchLogRecordProcessor(exporter)],
  });
  logs.setGlobalLoggerProvider(provider);
  return logs.getLogger('otel-log-emitter');
}

/**
 * Wrap `baseEmitter` with OTLP log export when a collector endpoint is configured.
 *
 * Opt-in and additive. With both `OTEL_EXPORTER_OTLP_LOGS_ENDPOINT` and
 * `OTEL_EXPORTER_OTLP_ENDPOINT` unset (the default — nothing prompts for it unless the OTel
 * scaffold question was answered yes), `baseEmitter` is returned UNCHANGED: no
 * `@opentelemetry/*` import is even attempted, so a project that declined the prompt never
 * pays for a dependency it did not install and never sends a byte over the network. With the
 * endpoint set, every call still reaches `baseEmitter` first (console stays console, null stays
 * null) and is ALSO forwarded to OTel once the dynamic import resolves.
 *
 * ⚠️ Fire-and-forget, deliberately — a failing or slow-loading exporter must never block or
 * throw for a caller of `debug`/`info`/`warn`/`error`. The one place a silently swallowed error
 * is correct, same as `otel_logging.py`'s `_install_otel_handler`.
 *
 * @param baseEmitter - The emitter every call still reaches (`CONSOLE_EMITTER`, `NULL_EMITTER`,
 *   or a host's own `LogEmitter`).
 * @returns `baseEmitter` itself when export is not configured or is refused; otherwise a new
 *   `LogEmitter` that forwards to both.
 */
export function withOtelLogExport(baseEmitter: LogEmitter): LogEmitter {
  const endpoint = resolveSignalOverride(
    process.env.OTEL_EXPORTER_OTLP_LOGS_ENDPOINT,
    process.env.OTEL_EXPORTER_OTLP_ENDPOINT,
  );
  if (!endpoint) {
    return baseEmitter;
  }

  const headersRaw = resolveSignalOverride(
    process.env.OTEL_EXPORTER_OTLP_LOGS_HEADERS,
    process.env.OTEL_EXPORTER_OTLP_HEADERS,
  );
  if (isCleartextWithCredentials(endpoint, headersRaw !== '')) {
    // The endpoint is named because the fix is to change it; the header VALUES never are —
    // they are the credential this guard exists to protect.
    baseEmitter.warn(
      'OTel log export refused: OTLP headers are set but the endpoint is neither https:// ' +
        'nor loopback, so credentials would cross the network in cleartext. Use an https:// ' +
        'endpoint, or drop the headers for a local collector.',
      { endpoint },
    );
    return baseEmitter;
  }

  let otelLogger: OtelLoggerLike | undefined;
  void installOtelLogger(endpoint, parseOtlpHeaders(headersRaw))
    .then((logger) => {
      otelLogger = logger;
    })
    .catch((error: unknown) => {
      baseEmitter.warn('OTel log export not started', { error: String(error) });
    });

  const forward = (
    level: 'debug' | 'info' | 'warn' | 'error',
    message: string,
    context?: Record<string, unknown>,
  ): void => {
    baseEmitter[level](message, context);
    otelLogger?.emit({
      severityText: level.toUpperCase(),
      severityNumber: OTEL_SEVERITY_NUMBER[level],
      body: message,
      attributes: context,
    });
  };

  return {
    debug: (message, context) => forward('debug', message, context),
    info: (message, context) => forward('info', message, context),
    warn: (message, context) => forward('warn', message, context),
    error: (message, context) => forward('error', message, context),
  };
}
