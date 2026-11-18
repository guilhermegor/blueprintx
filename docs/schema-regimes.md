# **Schema Regimes — the `pure-schema-regimes` Seam**

Explains `utils/schema_regimes.py`, shipped by every Python skeleton. Tracked as
[issue #1161](https://github.com/guilhermegor/blueprintx/issues/1161).

> **See also:** [Quality Rules](quality-rules.md) · [Decision Records](decision-records.md).

---

## The problem

A published series can change its columns mid-series. The CVM monthly fund profile is the
measured case:

| Period | Key column | Columns |
|--------|------------|---------|
| through `202311` | `CNPJ_FUNDO` | 106 |
| from `202312` | `TP_FUNDO_CLASSE` / `CNPJ_FUNDO_CLASSE` | 107 |

A reader written for one layout fails, or worse reads the wrong column, on the other. The
pattern that fixes it is a registry of per-regime windows, each naming the periods it covers,
with an adapter bound to one regime that refuses a period outside it.

## One implementation, in a package

That pattern used to ship twice in the templates (about 830 lines): once in `utils/` for all six
tiers and once, written separately, in the MVC tier's `model/`. Two copies drift, and every
generated project kept its own stale one. The logic now lives in the zero-dependency package
[`pure-schema-regimes`](https://pypi.org/project/pure-schema-regimes/), a sibling of
`pure-docs-br`, and each project keeps only a re-export seam, the same shape as
`utils/br_identifiers.py`:

```python
from utils.schema_regimes import RegimeRegistry, RegimeWindow

cls_registry = RegimeRegistry(
    [
        RegimeWindow(str_name="cnpj_keyed", int_period_start=None, int_period_end=202311),
        RegimeWindow(str_name="cnpj_classe_keyed", int_period_start=202312, int_period_end=None),
    ]
)
cls_registry.resolve(202311).str_name  # "cnpj_keyed"
cls_registry.resolve(202312).str_name  # "cnpj_classe_keyed"
```

The seam re-exports `RegimeWindow`, `RegimeRegistry`, `RegimeBoundAdapter` and
`SpecGapRegistry`. Ambiguous (overlapping) windows are rejected when the registry is built.

## Dropping the seam

Every tier declares `pure-schema-regimes` so a project that needs the pattern later already has
it. A project that never does should delete it. `bin/check_unreachable_modules.py` (the 1.0.0
release gate) never treats `utils/schema_regimes.py` as a root, so it reports the seam in every
tier while nothing imports it. Measured on the service tiers before the change: the gate
reported nothing, because every module under `utils/` was a public root. Dropping the seam
means deleting the file, its test and the dependency line.
