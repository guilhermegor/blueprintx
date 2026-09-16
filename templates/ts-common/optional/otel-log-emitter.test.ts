import { NULL_EMITTER } from './log-emitter';
import { isCleartextWithCredentials, resolveSignalOverride, withOtelLogExport } from './otel-log-emitter';

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

describe('isCleartextWithCredentials', () => {
  it('refuses an off-host http:// endpoint carrying credentials', () => {
    expect(isCleartextWithCredentials('http://collector.example.com:4318', true)).toBe(true);
  });

  it('allows http://localhost carrying credentials — the documented local-dev path', () => {
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
    expect(warnings.some((m) => m.includes('cleartext'))).toBe(true);
    expect(warnings.some((m) => m.includes('secret-token'))).toBe(false);
  });

  it('the positive-direction witness: an endpoint configured still forwards every call to baseEmitter', async () => {
    // @opentelemetry/* is not a devDependency of ts-common itself (it is added to a
    // scaffolded project only on the OTel opt-in — see bin/scaffold/ts_*.sh), so the dynamic
    // import inside installOtelLogger() rejects here. That is the real fire-and-forget path,
    // not a mock of it: base delivery must survive an exporter that never loads.
    process.env.OTEL_EXPORTER_OTLP_ENDPOINT = 'http://localhost:4318';
    const calls: Array<[string, Record<string, unknown> | undefined]> = [];
    const spyEmitter = {
      debug: (m: string, c?: Record<string, unknown>) => calls.push([m, c]),
      info: (m: string, c?: Record<string, unknown>) => calls.push([m, c]),
      warn: (m: string, c?: Record<string, unknown>) => calls.push([m, c]),
      error: (m: string, c?: Record<string, unknown>) => calls.push([m, c]),
    };

    const emitter = withOtelLogExport(spyEmitter);
    expect(emitter).not.toBe(spyEmitter);

    emitter.info('hello', { key: 'value' });
    expect(calls).toContainEqual(['hello', { key: 'value' }]);

    // Let the rejected dynamic import settle; the wrapper must not throw either way.
    await new Promise((resolve) => setTimeout(resolve, 0));
    emitter.info('still works after the exporter failed to load', undefined);
    expect(calls).toContainEqual(['still works after the exporter failed to load', undefined]);
  });
});
