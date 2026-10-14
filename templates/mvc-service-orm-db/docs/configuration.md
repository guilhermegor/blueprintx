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
| `APP_NAME` | yes | always | no | `mvc-service-orm-db` | `mvc-service-orm-db` | Service name used in logs. |
| `DB_BACKEND` | yes | always | no | `sqlite` | `postgresql` | One of `sqlite`, `postgresql`, `mariadb`, `mysql`, `mssql`, `oracle`. Read by `config/connection_db.py`. |
| `DB_PATH` | yes | `DB_BACKEND=sqlite` | no | `./data/app.db` | `./data/app.db` | SQLite database file. |
| `DB_USER` | yes | `DB_BACKEND` is not `sqlite` | yes | `user` | `user` | Database user. |
| `DB_PASSWORD` | yes | `DB_BACKEND` is not `sqlite` | yes | `password` | `password` | Replace the placeholder; never commit a real value. |
| `DB_HOST` | yes | `DB_BACKEND` is not `sqlite` | yes | `localhost` | `db.internal` | Database host. |
| `DB_PORT` | no | `DB_BACKEND` is not `sqlite` | no | per engine | `5432` | Left unset on purpose, see below. |
| `DB_NAME` | yes | `DB_BACKEND` is not `sqlite` | yes | `app` | `app` | Database name. Oracle uses `DB_SERVICE` instead. |
| `DB_DSN` | yes | `DB_BACKEND` is not `sqlite` | no | empty | `postgresql://u:p@h/db` | When set, replaces the individual fields. |
| `DB_SERVICE` | yes | `DB_BACKEND=oracle` | yes | `XEPDB1` | `XEPDB1` | Oracle service name; replaces `DB_NAME`. |
| `DB_ODBC_DRIVER` | yes | `DB_BACKEND=mssql` | no | `ODBC Driver 17 for SQL Server` | `ODBC Driver 18 for SQL Server` | ODBC driver name used to build the pyodbc connection string. |
| `DB_MSSQL_AUTH` | yes | `DB_BACKEND=mssql` | no | `sql` | `aad` | `sql` (UID/PWD) or `aad` (Azure AD Interactive). |
| `DB_ENCRYPT` | no | `DB_BACKEND=mssql` | no | driver default | `yes` | ODBC Driver 18 defaults to `Encrypt=yes`. Accepts yes/no/true/false/1/0/on/off plus the driver tokens strict, mandatory and optional. |
| `DB_TRUST_SERVER_CERTIFICATE` | no | `DB_BACKEND=mssql` | no | driver default | `yes` | Set when the server presents a self-signed certificate. |
| `SQL_ECHO` | yes | always | no | `false` | `true` | Echo SQL statements. |
| `SCOPE_FILTER_EXCLUDE_FII` | no | a scope filter uses it | no | unset (off) | `false` | Example kill switch, see below. |

## Why `DB_PORT` is left unset

`DB_PORT` is shared by six engines with different ports (postgresql 5432, mysql and mariadb 3306,
mssql 1433, oracle 1521). Seeding any one of them silently points the other five at the wrong
port, and a seeded wrong value beats the correct per-engine default the connection factory applies
when the variable is unset. Set it only to override that default.

## Scope-filter kill switches

A filter that removes records from a deliverable is a business decision, not a constant (see
`src/model/CLAUDE.md` for the incident and the three rules). Model each as one boolean named after
what it excludes, default off, the side that fails cheap: an unset or mistyped value excludes
nothing. Read it with
`model.scope_filter_example.resolve_kill_switch(str_env_var, bool_default=False)`.
Recognized tokens are `1/true/yes/on/y/t` (true) and `0/false/no/off/n/f` (false); anything else,
including unset, falls back to `bool_default`.
