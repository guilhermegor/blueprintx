
## OpenTelemetry log export (opt-in)

Added when the project was scaffolded with OTLP log export. These are the standard OpenTelemetry
variable names, read by the SDK itself. Leave `OTEL_EXPORTER_OTLP_ENDPOINT` empty to opt out:
with no endpoint, `otel_logging.py` never imports `opentelemetry` and never sends a byte over
the network, and the local `logging.FileHandler` is unaffected. The Python Logs signal has
"Development" status upstream (Traces and Metrics are Stable); see the module docstring of
`otel_logging.py` for the source and the fire-and-forget rationale that follows from it.

| Variable | In .env.example | Read when | Required | Default | Example | Notes |
|---|---|---|---|---|---|---|
| `OTEL_EXPORTER_OTLP_ENDPOINT` | yes | log export is wanted | no | empty (opted out) | `https://otlp.example.com` | Collector or provider endpoint. |
| `OTEL_SERVICE_NAME` | yes | endpoint is set | no | `unknown_service` upstream | the project name | Name it after the project. |
| `OTEL_EXPORTER_OTLP_HEADERS` | yes | endpoint is set | no | empty | `authorization=Bearer <token>` | Comma-separated `key=value` pairs. Never commit a real value: this file ships as `.env.example` too. When set, the endpoint must be `https://` or loopback, because OTLP/HTTP sends headers in cleartext over `http://`; `otel_logging.py` refuses to start the exporter and warns instead of leaking the credential. |
| `OTEL_EXPORTER_OTLP_LOGS_ENDPOINT` | no | endpoint for logs differs | no | the generic endpoint | `https://logs.example.com` | Overrides the generic endpoint for logs, with the same precedence the SDK uses. |
| `OTEL_EXPORTER_OTLP_LOGS_HEADERS` | no | headers for logs differ | no | the generic headers | `authorization=Bearer <token>` | Overrides the generic headers for logs. |
