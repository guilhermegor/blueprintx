# CLAUDE.md — migrations/

Migration conventions for this project.

## File naming

Migration slugs follow `verb_subject_detail` in snake_case, e.g.:
- `create_records_table`
- `add_status_column_to_users`
- `drop_legacy_sessions`

The `file_template` in `alembic.ini` prepends a sortable date prefix
(`YYYYMMDD`) for readability — no time component, since `rev` is already
unique and two migrations in the same day cannot collide on filename.
Migration order is always determined by `down_revision`, never by filename.

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

   `copy_from` is an argument to `batch_alter_table()` in the migration itself, so it
   cannot be configured in `env.py`. Either pass a complete `Table` to it, or accept
   that this migration is online-only — and say which, in the migration's docstring.

6. **Test both directions locally** before committing:
   ```bash
   poe migrate_up
   poe migrate_down
   poe migrate_up
   ```

7. **DDL and DML are both allowed in a migration, and a migration must be
   idempotent.** A data backfill or a schema change alike must be safe to re-run:
   - Guard every DML statement with a `WHERE` that makes re-running it a no-op
     (`UPDATE t SET col = v WHERE col IS NULL`), not a blind `UPDATE`/`INSERT`.
   - Batch a large backfill rather than one unbounded statement.
   - Sequence a schema change so data can land between steps: add the column
     **nullable**, backfill it, then a follow-up migration flips
     `nullable=False` — never all three in one migration that would fail
     partway on existing rows.
   - A `downgrade()` for a data migration may legitimately refuse rather than
     attempt a lossy reconstruction — `raise NotImplementedError("...")` (or
     `log + pass`) is correct **when the docstring says so and says why**. A
     silent `pass` with no explanation is not the same thing: rule 2 requires
     the function to exist, not that it pretend to reverse something it can't.

## Reference: a read-modify-write race, guarded at the schema level

`src/model/CLAUDE.md`'s "Read-modify-write races" section works through a stock
concurrency incident (a decrement racing another decrement) and its fix — pushing the
decision into the `UPDATE`'s own `WHERE` clause. The migration half of that fix belongs
here: add the invariant as a `CHECK` constraint so the database rejects what application
code failed to prevent, instead of it landing as a value nobody questions —
`op.create_check_constraint("ck_produto_estoque_non_negative", "produto", "estoque >= 0")`
in `upgrade()`, `op.drop_constraint(...)` in `downgrade()`.

## Workflow

```bash
# Create a new migration (autogenerate from ORM models)
poe migrate_new "describe_the_change"

# Apply all pending migrations
poe migrate_up

# Roll back one step
poe migrate_down

# Show current revision
poe migrate_current

# Show full migration history
poe migrate_history

# Generate the pending upgrade as offline SQL (no DB connection — for a DBA)
poe migrate_sql
```
