
## Multi-intent pipeline (opt-in)

Added when the project was scaffolded with multi-intent pipeline dispatch.

| Variable | In .env.example | Read when | Required | Default | Example | Notes |
|---|---|---|---|---|---|---|
| `PIPELINE_INTENT` | yes | multi-intent dispatch is wired | no | `send` | `reconcile` | Which purpose to run: `send` or `reconcile`, case-, accent- and spacing-insensitive. A typo fails loud. |
