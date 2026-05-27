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

5. **Test both directions locally** before committing:
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
make db_setup_schema   # or: poetry run alembic upgrade head

# Roll back one step
poetry run alembic downgrade -1

# Show current revision
poetry run alembic current

# Show full migration history
poetry run alembic history --verbose
```
