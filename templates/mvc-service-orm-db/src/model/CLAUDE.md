# CLAUDE.md — src/model/

The **model layer**: data access only. Each entity is one file holding its ORM-mapped class
and a service that opens sessions for writes and reads via the seam into a typed
`pandas.DataFrame` (every column typed on load via `apply_dtypes`). No rendering, no
orchestration, no business presentation. Keep `commit()` at the service boundary.

## Optional hexagonal seam — use only when a contract is genuinely shared

For most services the reference `example_entity.py` shape (an ORM model + a concrete service)
is enough — do **not** add ports/DTOs by default. Reach for the seam below only when a
contract is shared across modules or you need to swap the data source (real DB ↔ in-memory ↔
external API) without touching callers:

- **`model/ports/`** — `Protocol` interfaces an adapter must satisfy (structural typing; no
  inheritance, so a `MagicMock` satisfies a port in tests with zero setup).
- **`model/dtos/`** — frozen dataclass value objects (the shape that crosses the boundary),
  distinct from the ORM-mapped row.
- **Adapters at the model root** — concrete implementations of the ports (the only place
  that touches the session / ORM).

```python
# model/ports/note_repository.py
from typing import Protocol

class NoteRepository(Protocol):
	def fetch_all(self) -> "pd.DataFrame": ...
```

**Why "only when shared":** ports + DTOs are decoupling machinery with a real
indirection cost. Adding them to a single-consumer read is ceremony that obscures the
flow; adding them when three modules depend on one contract (or you mock it in many tests)
pays for itself. Default to the concrete entity; introduce the seam when the duplication or
the test-doubling actually appears.

## Naming & typing

Type every column on load (`apply_dtypes`, never pandas inference); normalise CNPJ/CPF via
`utils.br_identifiers` before any merge/compare; merge keys must share a dtype on both sides.

## Read-modify-write races (issue #385)

A transaction guarantees all-or-nothing, **not** exclusivity. `READ COMMITTED` — the default
isolation level on both PostgreSQL and MySQL — lets a second writer read the same row your
transaction just read, before either commits. A counter read in Python (`if estoque > 0:`)
then written back can have two concurrent callers each read the same value, each decide
independently that the write is safe, and each write — the row goes negative in silence, no
exception, no failed commit.

**Push the decision into the database**, so the row lock the `UPDATE` itself takes is what
serialises the writers:

```sql
UPDATE produto SET estoque = estoque - 1 WHERE id = ? AND estoque >= 1;
```

`rowcount == 0` **is** the "sold out" signal — check it, don't treat it as exceptional, and
never `SELECT` the value first and branch on it in Python (that reintroduces the race).

`SELECT ... FOR UPDATE` also serialises correctly but every contender queues behind the row
lock, costing throughput under contention. An optimistic `version` column
(`UPDATE ... WHERE version = ?`) avoids holding a lock but pushes the retry loop onto the
client — `rowcount == 0` means someone else won and the caller must retry the whole
read-modify-write. Neither replaces the arithmetic `WHERE` form above for a plain
increment/decrement.

Add `CHECK (estoque >= 0)` at the schema level regardless — it is the last line of defence,
turning a future silent `-7` into a raised error at the offending statement instead of a
number nobody questions. A worked example belongs with the Alembic migration scaffold (#381).
