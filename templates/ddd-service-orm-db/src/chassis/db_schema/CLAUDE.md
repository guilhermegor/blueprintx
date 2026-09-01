# CLAUDE.md — src/chassis/db_schema/

Shared SQL persistence chassis: `Base`, `DatabaseSession`, the `Repository` ABC, and the
reference `SQLAlchemyRecordRepository` (see the root `CLAUDE.md` for the layer table). This
leaf documents the one cross-cutting hazard every repository method here shares: two
concurrent read-modify-write calls racing on the same row.

## Read-modify-write races (issue #385)

A transaction guarantees all-or-nothing; it does **not** guarantee exclusivity. `READ
COMMITTED` — the default isolation level on both PostgreSQL and MySQL — lets a second writer
read the same row your transaction just read, before either commits. Two concurrent decrements
of a stock counter can each read `1`, each decide "there is stock" **in the application**, and
each write — both did the right thing alone, and the row goes negative in silence: no
exception, no failed commit, just a wrong number.

**The fix is a property of the SQL shape, not of the transaction boundary.** Move the decision
into the database so the row lock the `UPDATE` itself takes is what serialises the two writers:

```sql
UPDATE produto SET estoque = estoque - 1 WHERE id = ? AND estoque >= 1;
```

Check `rowcount` after executing it — `rowcount == 0` **is** the "sold out" signal, not an
exceptional condition to catch. Do not `SELECT` the value first and branch on it in Python;
that reintroduces the race the `WHERE estoque >= 1` clause exists to close.

### Two ways to serialise, and what each one costs

| Approach | Cost |
|---|---|
| `SELECT ... FOR UPDATE` then update | Serialises writers correctly, but every contender queues behind the row lock — pays in throughput under contention. |
| Optimistic lock: a `version` column, `UPDATE ... WHERE version = ?` | No lock held while the client thinks; loser's `rowcount == 0` and must retry the read-modify-write from the top. Fast under low contention, but the retry loop is the client's responsibility to write. |

Neither replaces the arithmetic `WHERE` clause above when the operation is a simple
increment/decrement — that form needs no row lock and no version column at all, because the
database re-evaluates `estoque >= 1` against whatever the current row holds, atomically.

### `CHECK` is the last line of defence, not the first

```sql
ALTER TABLE produto ADD CONSTRAINT ck_estoque_non_negative CHECK (estoque >= 0);
```

Add the constraint even when the `WHERE`-guarded `UPDATE` above is in place. If a future
call-site reintroduces the read-then-write race, the `CHECK` turns a silent `-7` into a raised
error on the offending statement — loss becomes a log entry instead of a number nobody
questions. A worked migration example belongs with the Alembic scaffold (#381), not here.

## `SQLAlchemyRecordRepository.update()` — lost update, not the negative-number shape

`repository.py`'s `update()` is a `session.get` → mutate → `flush()` read-modify-write, but it
has no arithmetic — two concurrent calls each overwrite the whole JSON blob, so the second
simply discards the first's change (last-write-wins), never a negative count. See the one-line
decision recorded at the call site in `repository.py`.
