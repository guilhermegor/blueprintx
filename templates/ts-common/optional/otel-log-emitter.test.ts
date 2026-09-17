import { NULL_EMITTER } from './log-emitter';
import type { LogEmitter } from './log-emitter';
import type { OtelLoggerLike } from './otel-log-emitter';
import {
  installOtelLogger,
  isCleartextWithCredentials,
  resolveOtlpLogsUrl,
  resolveSignalOverride,
  withOtelLogExport,
} from './otel-log-emitter';

// Layout-agnostic like otel_logging.py's test suite (blueprintx#438): these pure functions
// need no env mutation — the caller passes `process.env.X` in directly (see the module
// docstring for why the property access must stay literal at the real call sites).
describe('resolveSignalOverride', () => {
  it('prefers a set-but-empty signal value over the generic one', () => {
    // The negative control for the `??`-chain defect: `''` would be falsy-ish for an `||`
    // chain, so a naive fallback would use the generic value while the SDK — which keys on
    // presence — uses the empty override. The two would then disagree about the endpoint.
    expect(resolveSignalOverride('', 'http://generic.example:4318')).toBe('');
  });

  it('falls back to the generic value when the signal value is absent', () => {
    expect(resolveSignalOverride(undefined, 'http://generic.example:4318')).toBe(
      'http://generic.example:4318',
    );
  });
});

describe('resolveOtlpLogsUrl', () => {
  // CodeRabbit finding on PR #505: a generic-only endpoint was passed straight through as
  // the exporter's `url`, bypassing the SDK's own `/v1/logs` append — logs silently targeted
  // `/` instead of the collector's logs receiver.
  it('appends /v1/logs to a generic-only endpoint', () => {
    expect(resolveOtlpLogsUrl(undefined, 'http://localhost:4318')).toBe(
      'http://localhost:4318/v1/logs',
    );
  });

  it('does not double a trailing slash before appending', () => {
    expect(resolveOtlpLogsUrl(undefined, 'http://localhost:4318/')).toBe(
      'http://localhost:4318/v1/logs',
    );
  });

  it('uses the signal-specific value VERBATIM — no path is appended', () => {
    expect(resolveOtlpLogsUrl('http://localhost:4318/custom/logs/path', undefined)).toBe(
      'http://localhost:4318/custom/logs/path',
    );
  });

  it('a set-but-empty signal value wins and stays empty — no fallback, no path appended', () => {
    expect(resolveOtlpLogsUrl('', 'http://generic.example:4318')).toBe('');
  });

  it('returns empty when neither is set', () => {
    expect(resolveOtlpLogsUrl(undefined, undefined)).toBe('');
  });
});

describe('isCleartextWithCredentials — Node runtime (no window global)', () => {
  it('refuses an off-host http:// endpoint carrying credentials', () => {
    expect(isCleartextWithCredentials('http://collector.example.com:4318', true)).toBe(true);
  });

  it('allows http://localhost carrying credentials — the documented Node local-dev path', () => {
    expect(isCleartextWithCredentials('http://localhost:4318', true)).toBe(false);
  });

  it('allows an off-host http:// endpoint when no credentials are set', () => {
    expect(isCleartextWithCredentials('http://collector.example.com:4318', false)).toBe(false);
  });

  it('allows https:// regardless of host', () => {
    expect(isCleartextWithCredentials('https://collector.example.com:4318', true)).toBe(false);
  });

  it('refuses rather than throws on an unparseable endpoint carrying credentials', () => {
    expect(isCleartextWithCredentials('not a url', true)).toBe(true);
  });
});

describe('isCleartextWithCredentials — browser runtime (CWE-319 redirect hazard)', () => {
  // `fetch` (the ONLY transport the browser build can use) follows redirects with no config
  // knob to disable it (verified against OTLPExporterConfigBase's .d.ts — no `redirect`
  // option). So a browser runtime refuses every credentialed request, not just cleartext
  // ones: an https:// or loopback endpoint can still 3xx to an attacker-controlled cleartext
  // host, and fetch would resend the headers there. CodeRabbit finding on PR #505.
  const ORIGINAL_WINDOW = (globalThis as { window?: unknown }).window;

  beforeEach(() => {
    (globalThis as { window?: unknown }).window = {};
  });

  afterEach(() => {
    if (ORIGINAL_WINDOW === undefined) {
      delete (globalThis as { window?: unknown }).window;
    } else {
      (globalThis as { window?: unknown }).window = ORIGINAL_WINDOW;
    }
  });

  it('refuses credentials to an https:// endpoint — the HTTPS-to-HTTP redirect case', () => {
    expect(isCleartextWithCredentials('https://collector.example.com:4318/v1/logs', true)).toBe(
      true,
    );
  });

  it('refuses credentials to http://localhost too — a redirect target need not stay loopback', () => {
    expect(isCleartextWithCredentials('http://localhost:4318/v1/logs', true)).toBe(true);
  });

  it('still allows a request with no credentials — nothing for a redirect to leak', () => {
    expect(isCleartextWithCredentials('https://collector.example.com:4318/v1/logs', false)).toBe(
      false,
    );
  });
});

describe('withOtelLogExport', () => {
  const ORIGINAL_ENV = process.env;

  beforeEach(() => {
    process.env = { ...ORIGINAL_ENV };
    delete process.env.OTEL_EXPORTER_OTLP_ENDPOINT;
    delete process.env.OTEL_EXPORTER_OTLP_LOGS_ENDPOINT;
    delete process.env.OTEL_EXPORTER_OTLP_HEADERS;
    delete process.env.OTEL_EXPORTER_OTLP_LOGS_HEADERS;
  });

  afterEach(() => {
    process.env = ORIGINAL_ENV;
  });

  it('returns baseEmitter UNCHANGED when no endpoint is configured', () => {
    // The should-fail witness for "no import attempted": a project that never opted in gets
    // the exact same object back, never a wrapper — and every call still lands on it directly.
    const emitter = withOtelLogExport(NULL_EMITTER);
    expect(emitter).toBe(NULL_EMITTER);
  });

  it('warns via baseEmitter and returns it unchanged when the cleartext guard refuses', () => {
    process.env.OTEL_EXPORTER_OTLP_ENDPOINT = 'http://collector.example.com:4318';
    process.env.OTEL_EXPORTER_OTLP_HEADERS = 'authorization=Bearer secret-token';
    const warnings: string[] = [];
    const spyEmitter = { ...NULL_EMITTER, warn: (m: string) => warnings.push(m) };

    const emitter = withOtelLogExport(spyEmitter);

    expect(emitter).toBe(spyEmitter);
    expect(warnings.some((m) => m.includes('refused'))).toBe(true);
    expect(warnings.some((m) => m.includes('secret-token'))).toBe(false);
  });

  // The following tests use an INJECTED installer (the `install` parameter) instead of
  // relying on the real dynamic `@opentelemetry/*` import rejecting. CodeRabbit finding on
  // PR #505: the previous version depended on those packages being absent from ts-common's
  // own devDependencies to exercise the fallback — true here, but false the moment this file
  // is copied into an opted-in project (conditional_copy_otel adds the real packages), where
  // Jest could instead construct a REAL BatchLogRecordProcessor against http://localhost:4318,
  // making the test's outcome depend on network conditions in CI rather than on the code.
  // Injection makes both branches deterministic regardless of which environment runs them.
  function fakeInstaller(logger: OtelLoggerLike) {
    return () => Promise.resolve(logger);
  }

  function rejectingInstaller(reason: string) {
    return () => Promise.reject(new Error(reason));
  }

  it('forwards every call to baseEmitter immediately, before the installer settles', () => {
    process.env.OTEL_EXPORTER_OTLP_ENDPOINT = 'http://localhost:4318';
    const calls: Array<[string, Record<string, unknown> | undefined]> = [];
    const spyEmitter: LogEmitter = {
      debug: (m, c) => calls.push([m, c]),
      info: (m, c) => calls.push([m, c]),
      warn: (m, c) => calls.push([m, c]),
      error: (m, c) => calls.push([m, c]),
    };
    // Never resolves within this test — proves delivery to baseEmitter does not wait on it.
    const neverSettles = () => new Promise<OtelLoggerLike>(() => undefined);

    const emitter = withOtelLogExport(spyEmitter, neverSettles);
    expect(emitter).not.toBe(spyEmitter);
    emitter.info('hello', { key: 'value' });

    expect(calls).toContainEqual(['hello', { key: 'value' }]);
  });

  it('still delivers to baseEmitter after the injected installer REJECTS (deterministic fire-and-forget)', async () => {
    process.env.OTEL_EXPORTER_OTLP_ENDPOINT = 'http://localhost:4318';
    const calls: string[] = [];
    const warnings: string[] = [];
    const spyEmitter: LogEmitter = {
      debug: (m) => calls.push(m),
      info: (m) => calls.push(m),
      warn: (m) => {
        calls.push(m);
        warnings.push(m);
      },
      error: (m) => calls.push(m),
    };

    const emitter = withOtelLogExport(spyEmitter, rejectingInstaller('simulated load failure'));
    emitter.info('before settle');
    await new Promise((resolve) => setTimeout(resolve, 0)); // let the rejection settle
    emitter.info('after settle');

    expect(calls).toContain('before settle');
    expect(calls).toContain('after settle');
    expect(warnings.some((m) => m.includes('not started'))).toBe(true);
  });

  it('forwards to the resolved OTel logger too, once the injected installer RESOLVES', async () => {
    process.env.OTEL_EXPORTER_OTLP_ENDPOINT = 'http://localhost:4318';
    const emitted: unknown[] = [];
    const fakeLogger: OtelLoggerLike = { emit: (record) => emitted.push(record) };
    const baseCalls: string[] = [];
    const spyEmitter: LogEmitter = {
      debug: (m) => baseCalls.push(m),
      info: (m) => baseCalls.push(m),
      warn: (m) => baseCalls.push(m),
      error: (m) => baseCalls.push(m),
    };

    const emitter = withOtelLogExport(spyEmitter, fakeInstaller(fakeLogger));
    await new Promise((resolve) => setTimeout(resolve, 0)); // let the resolution settle
    emitter.info('hello', { key: 'value' });

    expect(baseCalls).toContain('hello'); // base emitter still runs — additive, never replaced
    expect(emitted).toContainEqual({
      severityText: 'INFO',
      severityNumber: 9,
      body: 'hello',
      attributes: { key: 'value' },
    });
  });
});

describe('installOtelLogger — real construction, no network export', () => {
  // Deliberately NOT mocked: constructing a LoggerProvider/OTLPLogExporter/BatchLogRecordProcessor
  // performs no network I/O by itself (a batch processor only sends on a later flush this test
  // never triggers), so this exercises the real @opentelemetry/* wiring. Only meaningful once
  // copied into an opted-in project (conditional_copy_otel adds the real packages) — inside
  // ts-common itself the dynamic import has nothing to resolve, so both branches are asserted.
  it('resolves to an emit-capable logger, or rejects — but never throws synchronously', async () => {
    const resultPromise = installOtelLogger('http://localhost:4318/v1/logs', {});
    expect(resultPromise).toBeInstanceOf(Promise);

    await resultPromise.then(
      (logger) => expect(typeof logger.emit).toBe('function'),
      (error: unknown) => expect(error).toBeDefined(),
    );
  });
});
