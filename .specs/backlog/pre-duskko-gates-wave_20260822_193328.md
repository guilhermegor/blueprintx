# Pre-duskko wave — gates: #207, #206, #110, #167, #139, #140, #163, #222

⚠️ **Scope grew during the session, by owner decision at each step.** Started as #167 +
three trivial ones; the owner then asked for the three boundary items (#139, #140, #163),
`poetry-plugin-shell`, and the ruff rules from the video tutorial (#222). Everything
delivered and verified with `scaffold_lint_test.sh`.

## Final state

| # | What | State |
|---|---|---|
| #207 | `bin/` outside ruff — 73 findings | ✅ 0 |
| #206 | `check-urls` skipped the delimiter line | ✅ + 2 real stale URLs fixed |
| #110 | `wwdates >=1.0.0` | ✅ (issue was stale: PyPI already has 2.0.0) |
| #167 | complexity gate | ✅ 80/80, gate green on both sides |
| #139 | import gate passed without looking | ✅ 4 new policies, fails instead of staying silent |
| #140 | direction between layers | ✅ 0 refactors (preventive) |
| #163 | 3 boundary rules | ✅ across the 5 tiers, as a decision test |
| #222 | ruff `W`(-W191) + `PL` + `PT` | ✅ 48 findings paid down |
| — | `poetry-plugin-shell` | ✅ + found 4/5 scaffolds weren't copying `requirements.txt` |
| — | `pytest.ini`: generic warning ignores | ✅ narrowed; opened **#223** |

## Issues opened along the way

- **#222** — ruff rules (closed on this branch)
- **#223** — `basic_conf` never closes the `FileHandler`; `ResourceWarning` invisible by
  construction (Python doesn't show it by default). Not fixed here: it's a behavior change
  in a helper that ships to every project.

## The thread running through this branch

Seven distinct defects, **the same class**: a gate reporting its own blindness as OK.

| where | how it showed up |
|---|---|
| #207 | the 16 files that ARE the quality machine were the only ones not linted |
| #206 | "All docstring URLs are reachable" over lines it never scanned |
| #167 (the gate itself) | reported green over 79 known violations, from **two** subshell causes |
| #139 | a silent `return 0` with no policy → 3 tiers with no boundary at all |
| #167 (hatch) | `ruff format` moved the marker and the hatch silently stopped counting |
| #222 | `--config lint.ignore` doesn't merge → a wrong measurement backed a wrong decision |
| pytest.ini | `ignore::DeprecationWarning` hid the warnings aimed at this code |

---

## (original ledger below)


**Created:** 2026-08-22 19:33 · **Branch:** `feat/complexity-gate-bin-lint-167`
**Base:** `v0.15.10` · **Owner decisions made this session** (see "Decisions" below)

⚠️ This ledger also answers the owner's triage question about 15 issues —
section **"Triage: what is pre-duskko and what is backfill"**, at the end.

---

## Owner decisions (2026-08-22, with measurement in hand)

**#167 — threshold policy: `tests=1`, `src=2`, `bin=8`.** Measured cost: **79 functions**
to refactor (38 in `tests/`, 39 in `src/`, 2 in `bin/`).

Measurement redone today on `templates/python-common` (`ruff C901`, the same implementation
that will measure in production — the trap #167 documents):

| threshold | `tests/` (378 fn) | `src/` (105 fn) | `bin/` (116 fn) |
|---|---|---|---|
| 1 | 38 (10%) | 67 | 99 |
| 2 | 11 (3%) | **39 (37%)** | 86 (74%) |
| 6 | — | 7 | 10 |
| **8** | — | 2 | **2** |
| 12 | — | 0 | 0 |

Matches the issue's 2026-08-16 table (8%/38%/71% → 10%/37%/74%): the tree moved a little,
and the combined number is still the one applied.

**Wave scope:** #167 + #110 + #206 + #207 together. All touch `templates/`, so all get more
expensive after `make new` — scaffolding is a one-shot copy (#109).

---

## Execution order

`#207 → #206 → #110 → #167`. #207 comes first because it's the one that makes ruff **lint
`bin/`**, where #167 is going to write `check_complexity.sh`; in the reverse order the new
gate would be born outside the lint.

---

## Slice 1 — #207: `bin/` is outside ruff ✅ DELIVERED

- [x] The reason written in the `exclude` is **half wrong**, and the measurement shows where

      ```toml
      # check tooling: ruff-format would tabify space-indented helpers and trip E101
      "bin",
      ```

      `bin/` is **already split** today — it isn't a homogeneous block of space-indented
      helpers:

      | indentation | files |
      |---|---|
      | tabs (house style) | `check_all_exports.py`, `check_comment_language.py`, `check_function_length.py` |
      | spaces | the other 10 |
      | **mixes both** | `check_review_threads.py` (337 tabs + 21 spaces) |

      The 27 `E101`s are **not** hypothetical and would **not** come from `ruff-format`: they
      already exist today, all in the one file that mixes. And the newer files
      (`check_function_length.py`, from #189) were already born with tabs — house style had
      already won inside `bin/`, the `exclude` just hid the scoreboard.

- [x] 73 findings behind the exclude, by rule — **all resolved, `bin/` is at 0**:

      | rule | n | nature |
      |---|---|---|
      | `E101` mixed-spaces-and-tabs | 27 | gone with `ruff format` |
      | `E501` line-too-long | 16 | mechanical |
      | `ERA001` commented-out-code | 15 | ⚠️ collides with **#169** (the ERA001 decision) |
      | `ANN202`/`ANN001` | 5 | missing annotation |
      | `S105` hardcoded-password-string | 3 | evaluate one by one |
      | `S607` start-process-with-partial-path | 2 | evaluate |
      | `UP038` non-pep604-isinstance | 2 | mechanical |
      | `S506` **unsafe-yaml-load** | 1 | **real defect** |
      | `D400` missing-trailing-period | 1 | mechanical |
      | `TID251` banned-api | 1 | evaluate |

- [x] ⚠️ Formatting `check_review_threads.py` here **diverges from the repo's copy** — this
      is exactly the debt from **#217** (two 524-line copies). Decide whether #217 lands in
      this wave or the file stays unformatted until then.

### How each class got resolved

| rule | n | resolution |
|---|---|---|
| `E101` | 27 → 4 | `ruff format bin` tabifies the **code**, but doesn't touch string content: the space-indented NumPy docstring became `TAB + 4 spaces` and E101 rose to **222**. `src/` has always used **tabs inside the docstring** (which is why `D206` is in `ignore`); an AST script converted only `bin/`'s docstring bodies, 222 → 4. The final 4 are pending markdown bullet indentation (`TAB + 2 spaces`) — deliberate, and `# noqa` doesn't exist inside a docstring → `bin/`'s `per-file-ignores`. |
| `ERA001` | 15 | **15/15 false positives**, all a comment-continuation line in prose. → `bin/`'s `per-file-ignores`, with the reason written in. Second independent measurement for #169 (0 true positives out of 24). |
| `E501` | 16 → 0 | 9 disappeared in the format; 7 rewritten by hand (all 100–101 chars). |
| `S105` | 3 | False positive by **name**: `_ALLOW_TOKEN`/`_READ_TOKEN`/`_STAMP_TOKEN` are source-text sentinels, not credentials. **Renamed to `_*_MARKER`** — a root fix, not `noqa`: the name misled the reader as much as bandit (same lesson as `CODERABBIT_TRIGGER_PAT`). |
| `S506` | 1 | False positive: `_MkDocsSafeLoader` **inherits from `yaml.SafeLoader`** (`check_docs_sections.py:52`) and resolves an unknown tag to `None`. ⚠️ The checkpoint called this "unsafe YAML load" — **it is not**; the comment above the call already explained it. `noqa` pointing at it. |
| `ANN202`/`ANN001` | 5 | Genuinely annotated (`types.ModuleType \| None`, `dict \| None`, `-> object` matching the docstring). |
| `S607` | 2 | `git` via PATH is resolution **by design** (the `git` the dev's shell and CI use). `noqa` with a reason. |
| `UP038` | 2 | `isinstance(x, (A, B))` → `A \| B`. |
| `D400` | 1 | Docstring's first line was a question; became a statement. |
| `TID251` | 1 | `FileContract` import **for annotation only**, the exact case `ruff.toml` itself documents → `# noqa: E402, TID251`. |

**Verification:** `ruff check bin` → `All checks passed!`; `ruff format --check bin` → 16 files already formatted; 87 gate tests pass.

⚠️ **Out of scope, measured and logged:** `bin/` is still **without mypy**. `mypy.ini` runs with `cd src`, so `bin/` never enters discovery. #207's "lint" half is delivered; the "type-check" half isn't, and it isn't 1 line (`bin/` isn't a package). Worth its own issue.

⚠️ The remaining 68 findings in `optional/` are **pre-existing** (identical before and after — checked with stash) and out of scope: `optional/` is template staging, it doesn't exist in a generated project.

## Slice 2 — #206: `check-urls` never reads a one-line docstring ✅ DELIVERED

- [x] Fixed: the `continue` on the delimiter line skipped the scan. Now `check_urls_in_line`
      runs **before** the state flip, on both branches (`"""` and `'''`).
- [x] **The bug was bigger than the issue** — and the measurement also corrected one of my
      assumptions. I had raised "three blind shapes"; the negative control showed **two**:

      | shape | blind before? |
      |---|---|
      | `"""one-line docstring with a URL"""` | ✅ yes (the one the issue reported) |
      | **opening** line of a multi-line docstring (`"""Summary … URL`) | ✅ yes, **not in the issue** |
      | **closing** line with text (`… URL"""`) | ❌ no |

      The closing case passed for a reason worth recording: the guard anchors on
      `^[[:space:]]*"""`, so a `"""` at the end of a line with text **is not recognized as a
      delimiter** — the URL got scanned as body (right answer, wrong mechanism) and the state
      never flips back to `false`, so everything after is read as if still inside the
      docstring. This **over-scans** (false positive), the opposite of #206's defect, and the
      NumPy convention closes on its own line — left as is, documented in the script instead
      of patched for the inverse failure.

- [x] **6 negative-control tests**, offline: they seed the hook's own cache (keyed by the
      URL's md5) instead of hitting the network. Sharper than a real fetch — **only a line the
      scanner actually read can query the cache**. 4 docstring shapes + a positive control
      (same fixture with 200 → passes) + a scope control (URL outside a docstring → ignored).
      Verified they fail on the script without the fix: 2 fail, exactly the 2 blind ones.
- [x] **The real 404s surfaced**, as the issue predicted — 2, both fixed:
      - `src/utils/sidecar_metadata.py:61` — `https://dados.cvm.gov.br/dados/FI/DOC/CAD` → **404**.
        Rewritten as host + path (the hook skips a host-only URL), following the convention
        `bin/CLAUDE.md` itself already stated.
      - `optional/webhook/infrastructure/slack_notifier.py:7` —
        `https://api.slack.com/messaging/webhooks` → **302**. Updated to the current 200 home
        (`https://docs.slack.dev/messaging/sending-messages-using-incoming-webhooks/`).
- [x] **Verification:** `src`, `bin`, `tests`, `optional` → all exit 0. shellcheck + `bash -n`
      clean; 40 integration tests pass.

## Slice 3 — #110: `wwdates >=1.0.0` ✅ DELIVERED

- [x] Bumped across the 4 service tiers (`ddd-*`, `mvc-*`), `>=` style per the issue's decision.
- [x] ⚠️ **The issue is stale on one factual point** and it's worth correcting there: it
      states that "`0.1.0` and `1.0.0` are the only releases". PyPI today has **`0.1.0`,
      `1.0.0`, `1.0.1`, `2.0.0`**. With an open floor, `>=1.0.0` resolves to **2.0.0** —
      another major, which is exactly the mechanism the issue feared (a major changing
      `DatesBRAnbima`'s meaning under the same name).
- [x] **Verified on the real wheels, not the README**, by downloading 1.0.0 and 2.0.0 from
      PyPI:
      - both export `DatesBRAnbima` from `wwdates/br/anbima.py`;
      - neither imports an HTTP client (`requests`/`urllib`/`httpx`) → genuinely offline;
      - `__init__` has only optional arguments → `DatesBRAnbima()` stays valid;
      - the 6 methods the wrapper calls exist in both.

      2.0.0's major is the **addition** of US calendars, not a change to this one. The bump
      is safe and the wrapper has **zero code diff**, as the issue predicted.
- [x] Fixed the **3 stale claims** in `src/utils/dates.py` that described 0.1.0's
      network-backed semantics (module docstring, singleton comment, `holidays()` docstring)
      — "lazily fetched", "network on first use, cached thereafter". A tracked doc outranks
      memory next session.

## Slice 4 — #167: complexity gate ✅ DELIVERED

- [x] `bin/check_complexity.sh` — two ruff invocations, mccabe not reimplemented.
- [x] Escape hatch `# complexity-ok: <reason>`, with the reason **mandatory** (a bare marker
      is rejected — the hatch exists for the sentence, not the marker).
- [x] Wired into **5** surfaces: pre-commit, `Makefile` (in `lint` + its own target), `tasks.sh`
      (function + `case` + sync), `bin/help.txt`, CI (`tests.yaml`).
- [x] 6 should-fail tests in `tests/integration/test_bin_scripts.py` (convention #111): fails
      above the ceiling, passes clean, honors a hatch with a reason, **rejects a hatch with no
      reason**, applies a different ceiling per tree, and **refuses to report success with
      zero files**.
- [x] **`tests/` — 39 of 39 refactored, ZERO hatches** (owner's decision: a stub goes to a
      module/fixture, not an escape hatch).
- [x] **`src/` — 39 of 39.** 28 genuinely refactored, 11 with a justified hatch.
- [x] **`bin/` — 2 of 2**, both refactored (no hatch).
- [x] Docs: `templates/python-common/CLAUDE.md` (gate line) + root `CLAUDE.md` (parity
      paragraph, next to the function-length gate).
- [x] Also wired **on BlueprintX's own side** via `--root .` (pre-commit `check-complexity` +
      the `complexity` job), the same one-implementation-only discipline #189 established.
      ⚠️ BlueprintX's own tree has no `src/` or `tests/`, so here it checks only `bin/` (2
      files): it earns its keep by traveling with the template it polices, not by the size of
      what it finds on this side.

### Where the hatch was used in `src/` (11), and why

| function | reason |
|---|---|
| `env_config.resolve_config_path` | each branch is a documented config failure, with its own message |
| `queries.load_query` | each branch is a lookup failure with its own remedy |
| `logs.CreateLog._validate_path` | two distinct validation gaps, each with its own message |
| `logs.CreateLog._caller_context` | walking the stack **is** the work |
| `logs.CreateLog._emit` | two destinations and one rejected level |
| `dtypes._validate_referenced_columns` | two distinct validation gaps |
| `http_downloader._assert_public_host` | **SSRF guard** — trading an auditable check for a shorter one isn't a trade this gate should win |
| `http_downloader._assert_url_allowed` / `_fetch_bytes` | input validation / transport error |
| `tabular_reader._cnpj_column_problem` / `decode_positional_payload` / `resolve_sheet_name` | rejection rules that cannot be collapsed |
| `retry` (3 functions) | see below |
| `outlook_gateway` (5 functions) | Windows COM with **non-fatal** degradation |

### ⚠️ Two threshold findings worth recording

1. **`src=2` is unreachable for a decorator factory, always.** It's three nested scopes by
   construction and mccabe **doubles the nested body into the enclosing scope's score** — the
   factory is charged for the wrapper's retry loop while containing no branch of its own. No
   arrangement drops below 3. This is the metric finding the idiom, not a code defect.
2. **The hatch broke when the formatter touched the file.** ruff anchors C901 on the `def`,
   but `ruff format` re-wraps a long signature and pushes the comment to the `)` line. A
   correctly written hatch silently stopped counting. Measured on `_validate_path`. The gate
   now scans the **whole signature**, bounded, and stops at its end — with two negative
   controls (a wrapped signature is honored; a marker in the **body** is not).

### Refactors that followed house rules (not contortions for a number)

- `decimals._parse` (8) and `dtypes._to_decimal` (7): `isinstance` chains → `singledispatch`,
  which is literally what `rules/python.md` mandates. The `bool` before `int` ordering, which
  the chain encoded via comment + position, now comes free from the MRO.
- `tabular_reader._read_raw_dispatch` (6): if-chain by extension → **dict dispatch**, the
  `common.md` rule for branching on a **value**. Adding a format became adding a key.
- `dtypes.apply_dtypes` (9): validation split from coercion; three mutating loops → one `.assign()`.
- `logs.initiate_logging` and `outlook_gateway._parse_env_bool`: a tri-state and two token
  sets became a **table**, which also becomes the single source of the valid values.

### 🐛 Real defects found along the way (not complexity-related)

- `logs.CreateLog._validate_path`: guards in the **wrong order** — `not path` came first, so
  a falsy non-string value (`0`, `[]`, `None`) got reported as "cannot be empty", sending the
  reader looking for an empty string that never existed. Type before empty.
- `decode_positional_payload`: now names the **first** overflowing position populated,
  instead of whichever the loop happened to raise on.

### ⚠️ ERA001 — the session's sixth measurement

The comments I wrote to explain the refactors repeatedly triggered `ERA001`; the isolated
trigger includes the word `returns` itself at the start of a sentence. `src/` and `tests/`
**keep** the rule (the ignore stayed scoped to `bin/`), so the cost is recurring and real —
more data for the **#169** decision.

### ⚠️ Two defects the gate itself had, and both were BLINDNESS

The first draft reported **"Cyclomatic complexity within limits (76 Python file(s))"** with
**79 known violations in the tree**. Two independent causes, both fixed and both documented
in the script:

1. `resolve_ruff` was called as `$(resolve_ruff)`. `resolve_poetry` populates the
   `POETRY_CMD` array, and **command substitution runs in a subshell** — so the array died
   right there, every subsequent `run_poetry` failed, and the `2>/dev/null || true` I had
   added swallowed the error. The gate reported a clean tree because it ran nothing. Now set
   as **global**.
2. The loop read `< <(run_ruff_c901 …)`. **Process substitution is also a subshell**: a hard
   failure in there could only `exit` the subshell, the loop would read empty, and the tree
   would report clean — the same blindness, a second time in the same file. Now the output
   goes to a file and is read synchronously, and a ruff exit **> 1** re-prints what ruff said
   and fails.

It's exactly the `export_deps.sh` lesson ("never diagnose a command whose output you
discarded") striking again, now inside the gate written to catch that kind of thing.

### ⚠️ Finding that corrects the approved cost table

The owner's decision was made on "38 functions with branching in `tests/`". Measuring
function by function, **13 of the 39 (33%) had no branching at all**: they were stubs/closures
`def`s nested inside the test, and **mccabe charges +1 to the enclosing function for each
nested `def`** (a `lambda` costs 0; a comprehension, `with`, `and`/`or`, ternary and `assert`
also cost 0). The threshold-1 argument — "a test with a branch tests two paths and the green
doesn't say which ran" — applied to none of them. The real branching cost was **26**, not 38.

Owner's decision on seeing the data: **move the stubs to a module/fixture, zero hatches in `tests/`.**

### Patterns used in `tests/` (all verified by measurement)

| was | became | why |
|---|---|---|
| nested `def fn_stub(...)` | a callable class or a module-level function | mccabe charges +1 to the enclosing test; the stub itself doesn't branch |
| a stub that branches per call | `Mock(side_effect=[...])` | the sequence becomes **data**; the `if` left the test body |
| `for x in (...)` with an assert | `@pytest.mark.parametrize` | the loop asserted N cases behind ONE green; now each case names itself in the report |
| `if not cond: pytest.skip()` | `@pytest.mark.skipif` | the condition is fixed at import time; it isn't a path *through* the test |
| skip based on a subprocess result | `_skip_unless` helper | genuinely runtime; a short-circuit instead of an `if` |
| `try/except ImportError` | `contextlib.suppress` | identical handling, `with` costs 0 |
| nested AST/discovery loops | comprehension | same discovery, cost 0 |
| `for h in logger.handlers: h.flush()` | **deleted** | `StreamHandler.emit()` already flushes — it was dead code |

⚠️ Two `list(map(lambda …))` written along the way were **reverted**: using `map` for a side
effect is the "clever" house style bans. They became `shutil.copytree` (which on top of that
can't forget the next extension) and three calls written out in full.

⚠️ **Fifth false-positive `ERA001` group this session**, now in the comments I wrote myself
to explain the refactors: eradicate reads `` `something` `` followed by `:` or `(` as code.
Rewritten in prose. `tests/` and `src/` **keep** the rule (the ignore stayed scoped to
`bin/`), so the cost is real and recurring — more data for the **#169** decision.

**Verification:** 381 tests pass, `ruff check tests` clean, `tests/` at zero on the gate.

---

## Triage: what is pre-duskko and what is backfill

Duskko is an **`mvc-service-native-db`**. There's one cutoff criterion: **does the item enter
`make new`'s one-shot copy?** If yes, it's cheaper before. If it only touches BlueprintX's own
repo, duskko doesn't inherit it and timing doesn't matter.

### Genuinely pre-duskko (touch `templates/`, duskko inherits)

| # | Why first |
|---|---|
| **#207** | `ruff.toml` is copied. Duskko is born with `bin/` blind. **In this wave.** |
| **#206** | Broken gate reporting green. Copied broken. **In this wave.** |
| **#110** | Service tier's `pyproject.toml`. 1 line. **In this wave.** |
| **#167** | `ruff.toml` + pre-commit + CI, all copied. **In this wave.** |
| **#116** | `utils/retry.py` → `retry/` package. An **import-path** change: after scaffolding it becomes a backfill in already-written code. Duskko is API ingestion — retry is the seam every network read uses. **Highest priority outside this wave.** |
| **#124** | `tests/CLAUDE.md` in the 4 tiers missing it. It's what Werner reads on day 1 to learn how to test here. Backfill is cheap (copy a file), but the cost of not having it is **precedent**. |
| **#155** | GitGuardian in the tiers' workflows. Missing secret scanning on day 1 is the worst moment to be missing it. |
| **#159** | New gate in `python-common`. Copied. |
| **#163** | Boundary rules in the tiers' `CLAUDE.md` — prose the new dev follows. Cheap backfill, but the same precedent argument as #124. |
| **#140** | Direction between layers in the import gate. `model/` can import `controller/` and passes. The gate's config is copied. |
| **#118** | `utils/ms_office` + `excel_sheet_names`. Only if duskko delivers Excel — a ready port (208 lines + 18 tests in `recon_al_cvm`). |
| **#121** | Email orchestration. Only if duskko reports by email. |
| **#117** | `read_xml` seam. **Ready, but duskko is JSON** — real value ≈ 0 for it. |
| **#111** | Half already shipped in #170. The other half (should-fail test on each `check_*.py`) is a copied `bin/` convention — and #167 already delivers one example of it. |

### Not pre-duskko (duskko doesn't inherit it)

| # | Why |
|---|---|
| **#139** | Layer map missing in **`ddd-*` ×2 and `lib-minimal`**. Duskko is **`mvc-service-native-db`**, which **already has** the layer map. Zero impact on it. Can wait, no rush. |
| **#169** | Audit of the quality gate's blind spots — analysis work on BlueprintX's own repo. Only becomes a template change once decided. ⚠️ But the **ERA001** part collides with #207's 15 findings above; that slice resolves itself in this wave. |

### Cut recommendation

If the goal is to scaffold soon: this wave (**#207, #206, #110, #167**) **+ #116** and done.
`#124`/`#163` are file copies, cheap to backfill. `#139` and `#117` don't touch duskko. The
rest (`#155`, `#159`, `#140`, `#118`, `#121`) is legitimate backfill while the project is
still small.

**Nothing here blocks `make new`** — the conclusion from ledger
`duskko-blockers_20260816_110000.md` still stands.
