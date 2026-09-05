# PR C — ingestion core (group 3 of duskko's section A)

**Created:** 2026-08-17 · **Base:** `main` @ `aaffe2b`
**Origin:** `duskko-section-a-execution_20260816_105855.md`, groups 1 and 2 already delivered (#180, #182)

Three issues that travel together because they touch the same ingestion seam in
`templates/python-common/src/utils/` and the same `src/config/CLAUDE.md`.

⚠️ **Scaffolding is a one-shot copy** (#109): whatever doesn't land before duskko's
`make new` becomes a manual backfill.

---

## Scope

| Issue | Topic |
|---|---|
| #120 | `raw_workspace` seam — bronze-artifact retention |
| #150 | daily on-disk cache for a vendor download, inside the seam |
| #128 | ingestion-contract discipline (8 lessons) + 2 executable gates |

## Measured current state

- `src/utils/raw_workspace.py` → **absent** (checked directly)
- `src/utils/sidecar_metadata.py` already **consumes** a `path_raw` — the seam that *produces*
  it was never delivered, so every reader would have to reimplement the same branch
- Exist: `http_downloader.py`, `retry.py`, `tabular_reader.py`, `zip_extractor.py`,
  `provenance.py`, `dtypes.py`, `frames.py`

---

## Execution

### #120 — `raw_workspace` — ✅ DELIVERED

- [x] `src/utils/raw_workspace.py` — a single point of truth for "where do this read's raw
      bytes live"
- [x] `path_raw=None` → `TemporaryDirectory`, no disk residue after the read
- [x] `path_raw=<dir>` → created with `parents=True` and **kept**, byte-for-byte
- [x] test for both branches, incl. the assertion that the temp dir **is gone** (runs OUTSIDE
      the `with` block; inside it proves nothing)
- [x] 🔴 `@contextmanager` stays **outside** `@type_checker`: in the reverse order the checker
      compares the `_GeneratorContextManager` against the `Iterator[Path]` annotation and
      **every** call raises `TypeError`. Amendment logged in the `runtime-type-checking` lesson.

### #150 — daily cache in the seam — ✅ DELIVERED

- [x] `src/utils/daily_cache.py` — on-disk cache keyed by the **data's reference date**,
      never wall-clock time (a run at 23:59 and one at 00:01 requesting the same reference
      day must hit the same file)
- [x] creates the parent folder instead of assuming the archiver already did
- [x] **logs which branch ran** (HIT vs. miss vs. bypass) — a silent cache is indistinguishable
      from a cache that never engaged, and "why is this data stale?" goes unanswered in the log
- [x] explicit `bool_use_cache` flag — cache policy belongs to the **caller**, not the client
- [x] **guards against a 0-byte file**: `write_bytes` is not atomic, so an interrupted run
      leaves an empty file, and serving it hands back a valid path to nothing
- [x] executable test that the drift job **does not** use the cache — today it is correct by
      **accident** (nobody wired the cache into it), and an accident reverts with one
      convenient import
- [x] docstring states the change granularity the cache assumes
- [x] 🔴 new lesson: `pythonpath = . src` loads each module **twice**, so a subclass coming
      from `src.utils.retry` is not the same class as `utils.retry` — the nominal check
      refuses it. See `two-import-paths-for-one-module-break-nominal-type-checks`.

### #128 — contract discipline + 2 gates — ✅ DELIVERED

- [x] `src/config/CLAUDE.md` gained the **"Reader-authoring discipline"** section with the 8
      rules no gate can check, plus the principle behind three of them: **cache/retry/timeout
      policy belongs to the CALLER, never the client** — the drift job, the probe and the
      daily ingestion talk to the same source and want three different policies
- [x] **`bin/check_all_exports.py`** — `__all__`-population gate. Walks the **FILES**, not the
      exports: a sweep that discovers the family *through* `__all__` cannot see the member
      missing from it (returns one item short and passes by not looking). Wired into the hook
      and CI, 8 tests, and **three controls**: green, red, and **refuses on empty discovery**
- [x] **`tests/unit/test_contract_family_conventions.py`** — the family invariants that
      per-contract tests structurally cannot reach: a unique `str_source_key`, no repeated
      column within one contract, and no column-name collision across contracts.
      Discovered via `pkgutil`, **not** via `__all__` — a hand-written collection is a hole at
      any scale — and fails if the roster comes back empty
- [x] ⚠️ the strong form of the collision gate (one source path ↔ one column name) needs a
      family where N readers project ONE file; the template ships only one contract, so it's
      documented in the test as the extension to make once the project grows. Logged as an
      honest limit, not a delivery.

---

## Verification run

- `bin/ci/scaffold_lint_test.sh` on **3 tiers**: `mvc-service-native-db` (293 unit + 30
  integration), `ddd-service-native-db` (288 + 30), `lib-minimal` (98 + 30) — real scaffold,
  `make lint` clean on all
- `check_test_copy_lists.py`: **31** shared tests reachable across the 5 tiers (was 27)
- negative control on each new gate, in both directions
- 🔴 the **local** ruff (0.15.14) did not catch the prose `ERA001` that the **project-pinned**
  ruff caught — checking against the version the project pins is not a formality

## Verification (every PR)

- `bash bin/ci/scaffold_lint_test.sh <tier>` on **each affected tier** — never just at the root
- Every new gate needs a **negative control** and an entry in the hand-maintained copy-list
- A gate lives on **4 surfaces**: hook, CI, `Makefile`, `tasks.sh`
