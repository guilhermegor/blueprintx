# Configuration

`.env.example` is the committed template for the git-ignored `.env`. Copy it to `.env` and adjust.
It holds keys and example values only; this table says what each variable means, and
`bin/check_env_docs_sync.py` in the BlueprintX repo fails when the file and the rows marked `yes`
differ.

`NODE_ENV` and `PUBLIC_PATH` are handled specially. Every other `KEY=VALUE` is inlined into app
code as `process.env.KEY` by webpack `DefinePlugin`. A real process environment variable (CI, or
a Docker BuildKit secret mounted at build time) overrides the value committed here.

## Variables

| Variable | In .env.example | Read when | Required | Default | Example | Notes |
|---|---|---|---|---|---|---|
| `NODE_ENV` | yes | build | no | `development` | `production` | `development` gives HMR and readable class names; `production` minifies and hashes CSS. The npm scripts set it through cross-env, so override it here only for ad-hoc local builds. |
| `PUBLIC_PATH` | yes | build | no | `/` | `/<repo-name>/` | Base public path the bundle is served from. The default fits local dev and root-served hosts; GitHub Pages project sites live under `/<repo-name>/`, so the deploy workflow sets it and `DefinePlugin` inlines it for react-router's `BrowserRouter` basename. |
| `API_KEY` | no | app code reads `process.env.API_KEY` | no | unset | `abc123` | Example of an app variable. Keep secrets out of git: set real values in the local `.env` (ignored) or pass them as a Docker BuildKit secret. |
