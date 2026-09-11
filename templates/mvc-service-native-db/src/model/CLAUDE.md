# CLAUDE.md — src/model/

The **model layer**: data access only. Each entity is one class per file; it opens the DB
(via `config.connection_db`), runs SQL, and returns a typed `pandas.DataFrame` (every column
typed on load via `apply_dtypes`). No rendering, no orchestration, no business presentation.

## Optional hexagonal seam — use only when a contract is genuinely shared

For most services the reference `example_entity.py` shape (a concrete class that reads and
returns a typed frame) is enough — do **not** add ports/DTOs by default. Reach for the
seam below only when a contract is shared across modules or you need to swap the data source
(real DB ↔ in-memory ↔ external API) without touching callers:

- **`model/ports/`** — `Protocol` interfaces an adapter must satisfy (structural typing; no
  inheritance, so a `MagicMock` satisfies a port in tests with zero setup).
- **`model/dtos/`** — frozen dataclass value objects (the shape that crosses the boundary),
  distinct from the raw row/frame.
- **Adapters at the model root** — concrete implementations of the ports (the only place
  that touches the DB driver).

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

## A filter that REMOVES rows from a deliverable needs a kill switch (blueprintx#161)

**Incident this convention comes from** (perfil_mensal_cvm, 2026-08-13): a hard-coded filter
dropped whole fund classes (FII/FIDC/FIP) from a regulatory delivery. A counterparty came
back demanding the fund that had silently left scope. **Sub-delivering costs ~R$500/fund/day;
over-delivering costs zero** — an asymmetry that was not encoded anywhere: no flag, no
explicit default, no measured price. When the rule needs to come back, that is a release;
when it is wrong, nobody notices until a counterparty is the one who does.

Three rules, demonstrated by `scope_filter_example.py`:

1. **A lone categorical field is not a fact.** The exclusion in the incident keyed on one
   column while the fund's own *name* said otherwise (named a "Fundo de Investimento em
   Direitos Creditórios", classified as `Ações`) — the record contradicted itself, and the
   filter was wrong in **both** directions it could have been read. Before keying a filter on
   one field, ask what else in the record asserts the same fact, and whether they can ever
   disagree.
2. **Ship it as a flag with a safe-side default, never as a bare deletion.** An `.env` flag
   lets production revert the rule without a release and makes the default explicit and
   reviewable. The default must be the side that fails cheap — for a scope-*narrowing* filter,
   that is "do not exclude". Corollary: an **unrecognised value resolves to the same safe
   side as unset** (see `resolve_kill_switch`), so a typo in `.env` cannot silently restore
   the expensive behaviour.
3. **Measure the price on real data and freeze it in a test.** Not "some rows changed" — an
   integration-level test should assert the exact before/after counts at the filter stage
   (the origin incident: 1952 → 2179 pre-delivery, 1790 → 2014 delivered, 208 of 224 added
   rows belonging to the counterparty who complained). `test_scope_filter_example.py` shows
   the unit-level shape of that assertion (`ScopeFilterPrice.int_rows_dropped`); scale the
   same pattern to your own filter's real counts.

See the root `CLAUDE.md`'s "Data-handling guardrails" for the one-paragraph pointer version,
and `.env.example` for the variable this pattern reads.
