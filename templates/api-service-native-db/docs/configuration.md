# Configuration

`.env.example` is the **seed** for `.env`. `bin/ensure_env.sh` copies it to `.env` on a fresh checkout and
then never touches `.env` again, so a machine set up months ago still carries its day-one values
however far the code has moved. Assume yours is stale and re-read this page whenever the backend
changes. Nothing checks `.env` at commit time; the runtime is the guard.

`.env.example` holds keys and example values only. This table is the single place that says what
each variable means, and `bin/check_env_docs_sync.py` (pre-commit and CI) fails when the file and
the rows marked `yes` in **In .env.example** differ in either direction.

The file lists the union of six backends' keys, so most of it is inert at any moment while still
reading as live configuration. **Read when** names the condition under which a variable is used;
outside it the variable is ignored, not wrong.

## Variables

| Variable | In .env.example | Read when | Required | Default | Example | Notes |
|---|---|---|---|---|---|---|
| `ENV` | yes | always | no | `development` | `development` | `dev` or `prd`; also accepts development, production and localized spellings, case-, accent- and space-insensitive. |
| `APP_NAME` | yes | always | no | `ddd-service-native-db` | `ddd-service-native-db` | Service name used in logs. |
| `DB_BACKEND` | yes | always | no | `sqlite` | `postgresql` | One of `sqlite`, `postgresql`, `mariadb`, `mysql`, `mssql`, `oracle`. SQL-backed backends only, for use with `chassis.db_schema`. |
| `DB_PATH` | yes | `DB_BACKEND=sqlite` | no | `./data/app.db` | `./data/app.db` | SQLite database file. |
| `DB_USER` | yes | `DB_BACKEND` is not `sqlite` | yes | `app_user` | `app_user` | Database user. |
| `DB_PASSWORD` | yes | `DB_BACKEND` is not `sqlite` | yes | `changeme` | `changeme` | Replace the placeholder; never commit a real value. |
| `DB_HOST` | yes | `DB_BACKEND` is not `sqlite` | yes | `localhost` | `db.internal` | Database host. |
| `DB_PORT` | no | `DB_BACKEND` is not `sqlite` | no | per engine | `5432` | Left unset on purpose, see below. |
| `DB_NAME` | yes | `DB_BACKEND` is not `sqlite` | yes | `app_db` | `app_db` | Database name. Oracle uses `DB_SERVICE` instead. |
| `DB_DSN` | yes | `DB_BACKEND` is not `sqlite` | no | empty | `postgresql://u:p@h/db` | When set, replaces the individual fields. |
| `DB_SCHEMA` | yes | `DB_BACKEND=postgresql` | no | `public` | `public` | Schema (search path). |
| `DB_SERVICE` | yes | `DB_BACKEND=oracle` | yes | `XEPDB1` | `XEPDB1` | Oracle service name; replaces `DB_NAME`. |
| `DB_ODBC_DRIVER` | yes | `DB_BACKEND=mssql` | no | `ODBC Driver 17 for SQL Server` | `ODBC Driver 18 for SQL Server` | ODBC driver name used to build the pyodbc connection string. |
| `ADMIN_EMAIL` | yes | docker-compose is included | no | `admin@app.local` | `admin@app.local` | Login for the database admin UI (pgAdmin or phpMyAdmin). |
| `ADMIN_PASSWORD` | yes | docker-compose is included | no | `changeme` | `changeme` | Replace the placeholder. |
| `ADMIN_PORT` | yes | docker-compose is included | no | `5050` | `5050` | Host port of the admin UI. |

## Why `DB_PORT` is left unset

`DB_PORT` is shared by six engines with different ports (postgresql 5432, mysql and mariadb 3306,
mssql 1433, oracle 1521). Seeding any one of them silently points the other five at the wrong
port, and a seeded wrong value beats the correct per-engine default the connection factory applies
when the variable is unset. Set it only to override that default.

## Engine selection

`chassis.db_schema.application.database_factory.active_backend()` is the single reader of
`DB_BACKEND`. It picks the handler and the SQL: queries are filed at
`src/config/queries/<DB_BACKEND>/`, so the value chooses the dialect that gets loaded. A value
with no matching directory fails at load and names the engines that do have one.
