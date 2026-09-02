# CLAUDE.md — alembic/

Migration conventions for this project.

## File naming

Migration slugs follow `verb_subject_detail` in snake_case, e.g.:
- `create_records_table`
- `add_status_column_to_users`
- `drop_legacy_sessions`

The `file_template` in `alembic.ini` prepends a sortable datetime prefix
(`YYYYMMDD_HHMM`) for readability. Migration order is always determined by
`down_revision`, never by filename.

## Autogenerate vs manual

| Change type | Approach |
|-------------|----------|
| Table create / alter / drop | `alembic revision --autogenerate` |
| Index add / drop | `alembic revision --autogenerate` |
| View create / drop | Manual — always use `op.execute()` |
| Stored procedure / function | Manual — always use `op.execute()` |
| Schema grant / revoke | Manual — always use `op.execute()` |
| Data backfill | Manual — always use `op.execute()` |

## Rules

1. **Never edit an applied migration.** Applied means `alembic current` shows
   its revision hash. Create a new migration instead.

2. **Always implement `downgrade()`** — even if it's a no-op (`pass`). Leaving
   it out silently breaks rollback.

3. **`upgrade()` and `downgrade()` must be inverses.** If `upgrade()` adds a
   column, `downgrade()` must drop it. Asymmetric migrations cause drift that
   is hard to diagnose.

4. **Views must be managed manually.** Alembic autogenerate does not detect
   views. Create them with `op.execute("CREATE OR REPLACE VIEW ...")` in
   `upgrade()` and `op.execute("DROP VIEW IF EXISTS ...")` in `downgrade()`.

5. ⚠️ **A `batch_alter_table` migration cannot be generated as offline SQL unless it
   passes `copy_from`.** On SQLite, batch mode rewrites the table (create temp → copy →
   drop → rename), and to emit that `CREATE TABLE` Alembic must know the table's full
   definition. Online it reflects the definition from the live database; with `--sql`
   there is no connection to reflect from, so it stops:

   ```
   This operation cannot proceed in --sql mode; batch mode with dialect sqlite requires
   a live database connection with which to reflect the table "pessoa". […] a complete
   Table object should be passed to the "copy_from" argument […]
   ```

   Measured on alembic 1.19.1 / SQLAlchemy 2.0.52: the same migration applies cleanly
   **online** and exits **255** offline, having written a `.sql` file holding only the
   `alembic_version` table — 8 lines, no `ALTER`. 🔴 **A pipeline that redirects the
   output and does not check the exit code keeps a truncated script that looks
   finished.** Always check the status, never just the file.

   `copy_from` is an argument to `batch_alter_table()` in the migration itself, so it
   cannot be configured in `env.py`. Either pass a complete `Table` to it, or accept
   that this migration is online-only — and say which, in the migration's docstring.

6. **Test both directions locally** before committing:
   ```bash
   poetry run alembic upgrade head
   poetry run alembic downgrade -1
   poetry run alembic upgrade head
   ```

## Schema search_path (PostgreSQL)

`env.py` reads `DB_SCHEMA` (default `public`) and sets `search_path` on the
connection. All migrations run inside that schema — qualify table names with
the schema only when referencing a *different* schema.

## Workflow

```bash
# Create a new migration (autogenerate from ORM models)
poetry run alembic revision --autogenerate -m "describe_the_change"

# Apply all pending migrations
bash bin/db_setup_schema.sh   # or: poetry run alembic upgrade head

# Roll back one step
poetry run alembic downgrade -1

# Show current revision
poetry run alembic current

# Show full migration history
poetry run alembic history --verbose
```
