
## OpenTelemetry log export (opt-in)

Added when the project was scaffolded with OTLP log export. These are the standard OpenTelemetry
variable names, resolved by `otel-log-emitter.ts` and never by the vendor SDK reading
`process.env` on its own in a browser build (see that file's module docstring). Leave
`OTEL_EXPORTER_OTLP_ENDPOINT` empty to opt out: with no endpoint, `otel-log-emitter.ts` never
imports `@opentelemetry/*` and never sends a byte over the network, and the base `LogEmitter`
is unaffected. The JavaScript Logs signal is "not yet stable" upstream (Traces and Metrics are
further along); the module docstring has the source and the fire-and-forget rationale.

| Variable | In .env.example | Read when | Required | Default | Example | Notes |
|---|---|---|---|---|---|---|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | yes | log export is wanted | no | empty (opted out) | `https://otlp.example.com` | Collector or provider endpoint. |
| `OTEL_SERVICE_NAME` | yes | endpoint is set | no | `unknown_service` upstream | the project name | Name it after the project. |
| `OTEL_EXPORTER_OTLP_HEADERS` | yes | endpoint is set | no | empty | `authorization=Bearer <token>` | Comma-separated `key=value` pairs. A browser bundle is public, so never put a credential here: anything inlined at build time is readable by every visitor. |
