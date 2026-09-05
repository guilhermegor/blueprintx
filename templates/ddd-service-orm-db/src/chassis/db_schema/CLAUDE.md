# CLAUDE.md — src/chassis/db_schema/

Shared SQL persistence chassis: `Base`, `DatabaseSession`, the `Repository` ABC, and the
reference `SQLAlchemyRecordRepository` (see the root `CLAUDE.md` for the layer table). This
leaf documents the one cross-cutting hazard every repository method here shares: two
concurrent read-modify-write calls racing on the same row.

## Read-modify-write races (issue #385)

A transaction guarantees all-or-nothing; it does **not** guarantee exclusivity. Neither
default isolation level prevents this, and they differ: PostgreSQL defaults to `READ
COMMITTED`, MySQL/InnoDB to `REPEATABLE READ`. ⚠️ The stronger level does not help — it
stabilises what your transaction *reads*, not what another writer *does* between your read and
your write. Under both, a second writer can read the same row your transaction just read. Two concurrent decrements
of a stock counter can each read `1`, each decide "there is stock" **in the application**, and
each write — both did the right thing alone, and the row goes negative in silence: no
exception, no failed commit, just a wrong number.

**The fix is a property of the SQL shape, not of the transaction boundary.** Move the decision
into the database so the row lock the `UPDATE` itself takes is what serialises the two writers:

```sql
UPDATE produto SET estoque = estoque - 1 WHERE id = ? AND estoque >= 1;
```

Check `rowcount` after executing it — but ⚠️ **`rowcount == 0` has TWO causes**: the `id`
matched no row, or it matched and the stock was insufficient. Collapsing them is the same
"two facts, one number" defect this whole page is about. Separate them explicitly:

```sql
UPDATE produto SET estoque = estoque - 1 WHERE id = ? AND estoque >= 1;   -- rowcount 0 or 1
SELECT 1 FROM produto WHERE id = ?;                                       -- only when 0
```

An existing row means sold out; no row means the id was wrong, which is a caller error and not
a business outcome. Do not `SELECT` the value first and branch on it in Python; that
reintroduces the race the `WHERE estoque >= 1` clause exists to close.

### Two ways to serialise, and what each one costs

| Approach | Cost |
|---|---|
| `SELECT ... FOR UPDATE` then update | Serialises writers correctly, but every contender queues behind the row lock — pays in throughput under contention. |
| Optimistic lock: a `version` column, `UPDATE … SET v = v + 1 WHERE id = ? AND v = ?` | No lock held while the client thinks; loser's `rowcount == 0` and must retry the read-modify-write from the top. Fast under low contention, but the retry loop is the client's responsibility to write. |

⚠️ **Both halves of that predicate are load-bearing.** Without `id = ?` the statement matches
every row at that version; without `SET v = v + 1` two concurrent writers both match the same
version and both succeed, which is precisely the race the version column exists to detect.

Neither replaces the arithmetic `WHERE` clause above when the operation is a simple
increment/decrement — that form needs no **explicit** `SELECT … FOR UPDATE` and no version
column, because the database re-evaluates `estoque >= 1` against whatever the current row
holds, atomically. It still takes a row lock for the duration of the write, as every `UPDATE`
does; what it avoids is holding one across a round trip to the client.

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
