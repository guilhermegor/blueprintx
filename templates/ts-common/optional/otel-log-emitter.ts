import type { LogEmitter } from './log-emitter';

const LOOPBACK_HOSTS = new Set(['localhost', '127.0.0.1', '::1', '[::1]']);

const OTEL_SEVERITY_NUMBER = { debug: 5, info: 9, warn: 13, error: 17 } as const;

export function resolveSignalOverride(
  signalValue: string | undefined,
  genericValue: string | undefined,
): string {
  if (signalValue !== undefined) {
    return signalValue.trim();
  }
  return (genericValue ?? '').trim();
}

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

function isBrowserRuntime(): boolean {
  return typeof window !== 'undefined';
}

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
    return true;
  }
  return !endpoint.startsWith('https://') && !LOOPBACK_HOSTS.has(hostname);
}

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

export type OtelLoggerInstaller = (
  endpoint: string,
  headers: Record<string, string>,
) => Promise<OtelLoggerLike>;

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
    resource: detectResources({ detectors: [envDetector] }),
    processors: [new BatchLogRecordProcessor(exporter)],
  });
  logs.setGlobalLoggerProvider(provider);
  return logs.getLogger('otel-log-emitter');
}

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
