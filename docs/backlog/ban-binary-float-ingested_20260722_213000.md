# Ban binary floats for ingested values + `check_dtypes` gate

Issue: #105. Backport of a defect found in `filings-b3` (PR #112, issue #40) before it could
reach the datalake. Sibling follow-up filed as `guilhermegor/filings-cvm#157`.

## The defect

An ingestion scaffold let a generated project type a monetary column `float64` with nothing
objecting. Measuring showed the loss happens **upstream of the dtype**:

```python
json.loads('{"v": 1984223115.42}')["v"]   # -> float already holding
                                          #    1984223115.4200000762939453125
```

so changing the dtype alone would fix nothing. The error is far below a cent per value — which
is why nobody catches it: the frame prints correctly, every single-value test passes, and no
contract check fires. It surfaces later as a reconciliation against the source's own published
totals missing by a hair, in data already in bronze and expensive to re-ingest.

## Done — all in `templates/python-common/`

- [x] `src/utils/dtypes.py` — `list_decimal_cols` beside `list_date_cols`, plus `_to_decimal`.
      Preserves the **source's own scale** (`"1.50"` stays 2dp, `"1.5000"` stays 4dp); no
      precision is chosen, because choosing one is a silver/gold decision.
- [x] `_to_decimal` **refuses a `float`** rather than converting it — converting launders a lossy
      value into a type advertising exactness, worse than the float because nothing downstream
      questions it. `NaN` is recognised as *missing* first (NaN is a float and is pandas' missing
      marker, so blank cells would otherwise raise).
- [x] `src/utils/tabular_reader.py` — threaded through `read_table` and `_finalize`.
- [x] `bin/check_dtypes.py` — structural gate, `check_typing`/`check_provenance` pattern, with a
      reason-carrying `# dtype-ok: <why>` escape hatch. **Ruff cannot do this**: `banned-api`
      matches imports and attribute access, not a `"float64"` string literal in a dtypes dict.
- [x] Wired into **both** `.pre-commit-config.yaml` and `.github/workflows/tests.yaml` — CI runs
      gates as explicit steps, so a hook-only gate dies to `--no-verify` while branch protection
      runs the workflow.
- [x] 5 decimal tests appended to `tests/unit/test_dtypes.py`, asserting **exact equality**
      (`pytest.approx` would defeat the purpose) and the float refusal.
- [x] Gate indentation normalised to 4 spaces, matching its `bin/` siblings (`bin/` is
      ruff-excluded, so this is convention, not tooling).

## Verification — the real harness, per `verify-template-changes-with-the-real-ci-harness`

| Skeleton | Result |
|---|---|
| `lib-minimal` | scaffolds clean, lints clean, 43 tests pass |
| `mvc-service-native-db` | scaffolds clean, lints clean, **193 tests pass** (`test_dtypes.py` 14) |

Gate mutation-tested inside the scaffolded tree: injecting `{"VLM": "float64"}` → **exit 1**;
same line with `# dtype-ok: dimensionless statistic` → **exit 0**.

## Noticed, not fixed (out of scope)

- **`lib-minimal` ships `src/utils/dtypes.py` but no `tests/unit/test_dtypes.py`**, so the seam
  is untested in that tier — confirmed downstream, where `filings-b3` had no dtype tests at all
  and needed a new file. Worth its own issue: a shipped seam with no test in the tier that ships
  it is exactly how a regression gets through.
- `templates/python-common/src/utils/sidecar_metadata.py` still exports the CVM-branded
  `cvm_meta_url()` — see lesson `template-reference-impls-must-be-domain-neutral`.
