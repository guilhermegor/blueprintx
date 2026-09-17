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
 * has no `process.env`. So this file resolves the endpoint (`resolveOtlpLogsUrl`) and headers
 * (`resolveSignalOverride`) itself, mirroring the Python port's precedence, and passes them
 * EXPLICITLY to the exporter, rather than leaving the SDK to read them — the opposite of what
 * `otel_logging.py` does, and deliberately so: relying on the SDK's own read would silently do
 * nothing in the browser. `process.env.<KEY>` is written as a literal member access (never a
 * computed lookup) because that is the exact shape react-spa-webpack's `webpack.config.js`
 * already replaces at build time via `DefinePlugin`, one entry per `.env` key — ts-lib reads
 * the same literal from the real `process.env` at runtime. One resolution path, both runtimes.
 *
 * ⚠️ THIRD: `otel_logging.py` hardens its `requests` session against a credential-forwarding
 * redirect (CWE-319, `max_redirects = 0`). This module CANNOT do the equivalent for the
 * BROWSER transport — it sends via `fetch`, which follows redirects by default, and
 * `OTLPExporterConfigBase` (the exporter's own config type, verified against its `.d.ts`)
 * exposes no `redirect` option to disable that. There is also no way to intercept it without
 * monkey-patching the GLOBAL `fetch`, which would affect requests this module does not own.
 * Node's transport (`http`/`https` core modules) does not auto-follow redirects, so the hazard
 * is browser-only — and because it cannot be closed at the transport, `isCleartextWithCredentials`
 * below refuses EVERY credentialed request in a browser runtime, not only cleartext ones: an
 * https:// or loopback endpoint can still 3xx to an attacker-controlled cleartext host, and
 * `fetch` would resend the headers there. This is also what `otel.env.fragment` already tells
 * react-spa-webpack projects to do architecturally (route through a same-origin collector PROXY
 * that injects the real credential server-side) — this guard enforces it instead of merely
 * documenting it.
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
 * Resolve the LOGS OTLP endpoint as the exact URL the exporter must request.
 *
 * Per the OTel spec, `OTEL_EXPORTER_OTLP_LOGS_ENDPOINT` (signal-specific) is used VERBATIM as
 * the full request URL, while `OTEL_EXPORTER_OTLP_ENDPOINT` (generic) is a BASE the signal
 * path must be appended to — the SDK does this itself when it reads the variable, but this
 * module passes `url` explicitly (see the module docstring's SECOND measurement), so it has
 * to replicate that one step or a generic-only endpoint silently exports to `/` instead of
 * `/v1/logs` (CodeRabbit finding, PR #505).
 *
 * @param signalValue - `process.env.OTEL_EXPORTER_OTLP_LOGS_ENDPOINT`.
 * @param genericValue - `process.env.OTEL_EXPORTER_OTLP_ENDPOINT`.
 * @returns The exporter-ready URL; `''` when neither is set.
 */
export function resolveOtlpLogsUrl(
  signalValue: string | undefined,
  genericValue: string | undefined,
): string {
  if (signalValue !== undefined) {
    return signalValue.trim();
  }
  const generic = (genericValue ?? '').trim();
  if (!generic) {
    return '';
  }
  return `${generic.replace(/\/+$/, '')}/v1/logs`;
}

// Evaluated per call, not frozen at module load, so a test can simulate "browser" by
// setting `globalThis.window` before calling `isCleartextWithCredentials` — a module-level
// `const` snapshot taken at import time would not see that mutation.
function isBrowserRuntime(): boolean {
  return typeof window !== 'undefined';
}

/**
 * Report whether credentials would be sent somewhere a redirect could leak them.
 *
 * In a BROWSER runtime this refuses every credentialed request outright, cleartext or not
 * (see the module docstring's THIRD measurement) — `fetch` follows redirects with no way to
 * disable it here, so even an https:// or loopback endpoint cannot be proven safe. In Node,
 * where the transport does not auto-follow redirects, the narrower cleartext-off-host check
 * applies, same as `otel_logging.py`'s `_is_cleartext_with_credentials`.
 *
 * @param endpoint - The effective OTLP logs endpoint (path already appended, if applicable —
 *   see `resolveOtlpLogsUrl`; a path suffix does not change the scheme/host this checks).
 * @param hasHeaders - Whether `OTEL_EXPORTER_OTLP_[LOGS_]HEADERS` carries anything.
 * @returns `true` when the exporter must not be started.
 */
export function isCleartextWithCredentials(endpoint: string, hasHeaders: boolean): boolean {
  if (!hasHeaders || !endpoint) {
    return false;
  }
  if (isBrowserRuntime()) {
    return true;
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

export interface OtelLoggerLike {
  emit(record: {
    severityText: string;
    severityNumber: number;
    body: string;
    attributes?: Record<string, unknown>;
  }): void;
}

/** The shape `withOtelLogExport` needs from its installer — real or injected for a test. */
export type OtelLoggerInstaller = (
  endpoint: string,
  headers: Record<string, string>,
) => Promise<OtelLoggerLike>;

/**
 * Build the OTel logger provider and return a minimal emit-capable logger.
 *
 * Split out of `withOtelLogExport` so the dynamic import — the one place this package touches
 * `@opentelemetry/*` — is a single, separately awaitable async function, never inlined into
 * the fire-and-forget wrapper below. Exported (not just passed as `withOtelLogExport`'s
 * default `install` parameter) so a test can exercise real `@opentelemetry/*` construction —
 * which performs no network I/O; only a later batch flush from the returned logger would —
 * separately from `withOtelLogExport`'s own contract, which a test instead verifies with an
 * INJECTED installer (see that function's `install` parameter).
 */
export async function installOtelLogger(
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
 * @param install - Builds the real OTel logger; overridable so a test can inject a
 *   deterministic fake instead of relying on `@opentelemetry/*` being resolvable (it is not,
 *   inside `ts-common` itself — see `installOtelLogger`'s own docstring). Defaults to the real
 *   `installOtelLogger`.
 * @returns `baseEmitter` itself when export is not configured or is refused; otherwise a new
 *   `LogEmitter` that forwards to both.
 */
export function withOtelLogExport(
  baseEmitter: LogEmitter,
  install: OtelLoggerInstaller = installOtelLogger,
): LogEmitter {
  const endpoint = resolveOtlpLogsUrl(
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
    // they are the credential this guard exists to protect. The reason text covers both
    // refusal paths isCleartextWithCredentials can take (browser: any credentials at all;
    // Node: only a cleartext off-host endpoint) rather than naming just one.
    baseEmitter.warn(
      'OTel log export refused: OTLP headers are set, and either this is a browser runtime ' +
        '(fetch follows redirects with no way to disable it here, so no credentialed request ' +
        'is safe) or the endpoint is neither https:// nor loopback (credentials would cross ' +
        'the network in cleartext). Route through a same-origin collector proxy instead, use ' +
        'an https:// endpoint, or drop the headers for a local collector.',
      { endpoint },
    );
    return baseEmitter;
  }

  let otelLogger: OtelLoggerLike | undefined;
  void install(endpoint, parseOtlpHeaders(headersRaw))
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
