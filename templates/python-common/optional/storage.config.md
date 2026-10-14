
## Schema-less storage (opt-in)

Added when the project was scaffolded with the schema-less backends (`chassis.db_wschema`).

| Variable | In .env.example | Read when | Required | Default | Example | Notes |
|---|---|---|---|---|---|---|
| `STORAGE_BACKEND` | yes | storage is included | no | `json` | `joblib` | One of `json`, `csv`, `joblib`. |
| `DATA_DIR` | yes | storage is included | no | `./data` | `./data` | Directory holding the storage files. |
| `DB_FILE_JSON` | yes | `STORAGE_BACKEND=json` | no | `records.json` | `records.json` | JSON file name inside `DATA_DIR`. |
| `DB_FILE_CSV` | yes | `STORAGE_BACKEND=csv` | no | `records.csv` | `records.csv` | CSV file name inside `DATA_DIR`. |
| `JOBLIB_DIR` | yes | `STORAGE_BACKEND=joblib` | no | `artifacts` | `artifacts` | Directory for joblib artifacts. |
| `JOBLIB_SECRET_KEY` | yes | `STORAGE_BACKEND=joblib` | no | empty | a hex string | Set a hex string in production to enable HMAC tamper detection. |
