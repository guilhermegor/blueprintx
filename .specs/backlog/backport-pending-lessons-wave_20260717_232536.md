# Backport wave — pending BlueprintX lessons → templates

Created 2026-07-17. Tracks the backport of every lesson in the global store
(`~/.claude/memory/lessons/`) that was **not yet applied** as of the mirror's last
recorded backport (filings-cvm batch + mypy fix, 2026-07-08). Each lesson has a GitHub
issue (assigned, on `blueprintx kanban` #8, Backlog) — file one branch/PR per lesson (or
per tight cluster) as it is pulled.

**Do NOT delete this file when every box is `[x]`** — keep it as a permanent record
(see the "keep completed backlogs" rule). Tick the last box + add a "Completed — kept as
a record" note instead.

## ★ SOLVE FIRST — checkpoint 2026-07-18

Two issues from the `pyty` design discussion take **priority over the whole backport wave
below**. Do these first, in order:

1. **[x] #76 — DONE (branch `refactor/76-beartype-typing-engine`).** Backed the runtime
   type-checking engine with **beartype**, behind the same seam names. Decisions applied:
   `violation_type=TypeError` (mandatory), strict bool via `hint_overrides`
   (`Annotated[int | np.integer, Is[not bool]]`), Mock leniency **dropped** (use `Mock(spec=...)`),
   `@runtime_checkable` added to both Protocol ports (beartype fails at decoration on a plain
   Protocol). beartype declared a main dep in all 5 tiers; engine got its first test suite.
   Return-type checking is now on (old engine checked args only) — surfaced + fixed a
   type-dishonest `test_dates.py` stub. **Verified: all 5 tiers scaffold clean, `make lint`
   unchanged, unit tests pass** (lib-minimal 3, mvc 128, ddd 123). Original verdict retained
   below for the record:
   *A `pyty` library is **not** warranted — the
   vendored engine is a shallow, slower subset of beartype (no dict/tuple/set element checks,
   shallow TypedDict, no return-type/nested-generic/TypeVar), and it has **zero external
   consumers** (every importer is a scaffold carrying its own vendored copy). So: keep it
   vendored, stop hand-maintaining a shallow checker, back it with beartype. Decide the 3 policy
   divergences (Mock-skip, numpy-int leniency, bool-vs-int strictness).
   **⚠ Migration blocker (measured against beartype 0.22.9):**
   `BeartypeCallHintParamViolation` is **not** a `TypeError` subclass, so a naive swap breaks
   every `pytest.raises(TypeError)` in the scaffolded projects — `BeartypeConf(violation_type=
   TypeError)` is **mandatory**. numpy leniency is cleanly solved by `hint_overrides=
   BeartypeHintOverrides({int: int | np.integer})` (verified); Mock-skip has **no** conf knob.
2. **[x] #77 — DONE (branch `feat/77-vscode-static-validation`).** Shipped `.vscode` static
   validation: `python.analysis.typeCheckingMode: strict` (Pylance) + Ruff format/autofix/
   organise-imports on save, scoped to `[python]`, in `templates/python-common/.vscode/
   settings.json`; new `.vscode/extensions.json` (ruff + python + pylance) wired into all 5
   Python scaffolds. **Also fixed a pre-existing defect:** the shipped `check-json` pre-commit
   hook only excluded `.vscode/settings.json`, but the per-tier `tasks.json` (and now
   `extensions.json`) are JSONC too — broadened the exclude to `^\.vscode/.*\.json$`. tier
   `CLAUDE.md` updated. **TS parity deferred** (issue said optional) — `templates/ts-common/
   .vscode/` could get ESLint/TS-server-on-save later; not filed as its own issue yet.

3. **[x] #82 — DONE (PR #86, squash `e7fa62e`).** Externalised the beartype typing
   **policy** from `validate.py` into a documented, editable `optional/typing/policy.py` seam:
   `VIOLATION_TYPE` (⚠ load-bearing — kept `TypeError`), `STRICT_BOOL`, `WIDEN_INT_TO_NUMPY`, and
   `PEP484_NUMERIC_TOWER` (opt-in) knobs feed `build_conf()`; `validate.py` stays a thin adapter that
   imports `CONF`. A new `test_policy_seam_knob_flip_changes_behaviour` proves flipping `STRICT_BOOL`
   on the seam changes runtime behaviour with the adapter untouched. **Also fixed:** shared-engine
   docstrings must not hardcode one layout's FQN `:mod:` path — lib's anchored sed only rewrites
   `from/import` lines, so a `chassis.typing.*` doc ref would ship stale to a lib project; de-FQN'd to
   bare module names. **Verified:** MVC (`utils.typing`), DDD (`chassis.typing`), lib
   (`_internal.utils.typing`) all scaffold, `make lint` clean (tree unchanged), unit tests pass
   (mvc 10, ddd 10, lib 3); knob-flip test green in both service layouts.

(Then #48 mike (#84), #83 mike-services (#85), then the wave below.)

## How this wave was scoped

- Source: 129 files in `~/.claude/memory/lessons/`.
- Boundary: the mirror `docs/blueprintx-lessons.md` records everything backported through
  2026-07-08. Pending = origin ≥ 2026-07-09 **plus** the undated-recent tail (automation /
  release / docs-api wave, origins 07-11…07-17).
- Result: **28 lessons**, issues **#48–#75**.

## Definition of done (per lesson)

1. Apply the lesson to the relevant `templates/**` (and `bin/scaffold/*.sh` where the
   scaffold must emit it).
2. Verify in a freshly scaffolded tree (`make lint` + `make unit_tests`), not just at
   template root.
3. Mark it applied in the mirror `docs/blueprintx-lessons.md`.
4. Tick its box here; `Closes #<N>` in the PR body.

## Docs / site

- [x] #48 — **DONE (PR #84, squash `dd7f730`)** — mike doc versioning shipped **library-first**,
      not all-tier: `mike` + `extra.version.provider` in lib-minimal, `docs.yaml` → strict build
      check, `deploy_docs` job in `release-pypi.yaml` (after the PyPI publish, X.Y granularity,
      prerelease-guarded), and the shared `bin/enable_pages.sh` made **model-aware** (mike →
      gh-pages branch source, guarded until that branch exists; else Actions). ⚠️ The lesson is
      tagged `python-common` but a service is *deployed, not published*, so the "pinned consumer
      needs old docs" rationale does not apply — **the service-tier decision was #83**.
- [x] #83 — **DONE (PR #85, squash `58798a0`)** — user chose **Option B**:
      extend mike to **all 4 service tiers**, not lib-minimal-only. `mike` dep + `extra.version.
      provider: mike` added to each service `pyproject.toml`/`mkdocs.yml`; the shared
      `templates/common/docs_version/docs.yaml` converted to **strict-build-only** (no deploy); a
      `deploy_docs` mike job added to `templates/python-common/.github/workflows/release.yaml`,
      gated on the **tag job** (services have no PyPI publish), prerelease-skipped in-step, and
      regenerating `CHANGELOG.md` before deploy. `bin/enable_pages.sh` needed no change (already
      model-aware from #48). Tier `contributing.md` rewritten Actions→mike. **Verified:** all 4
      service TOML/YAML parse, offline scaffold emits the mike wiring, `mkdocs build --strict`
      passes on a generated mvc-native tree (mike is deploy-time-only, absent at build).
- [x] #49 — **DONE (branch `feat/docs-site-cluster-49-51`, PR #95)** — the existing `logo_lorem_ipsum.png` placeholder is copied to `docs/assets/logo.png` and wired as `theme.logo` + `theme.favicon` and a landing `<img class="hero-logo">` on `docs/index.md`; size/placement tunable in the new shared `docs/stylesheets/extra.css`; swap note in `contributing.md`. Verified: `mkdocs build --strict` clean (asset paths resolve).
- [x] #50 — **DONE (same branch, PR #95)** — `docs/api.md` → `docs/api/` (`index.md` overview documenting the grouping discipline + `reference.md`) in all 5 tiers; nav is an API Reference **section**; scaffolds copy the directory; all cross-links fixed (`(api.md)`→`(api/index.md)`; `reference.md` intra-doc links →`../`). Verified strict-build clean.
- [x] #51 — **DONE (same branch, PR #95)** — `bin/check_docs_sections.py` (pre-commit `check-docs-sections` + CI, gate parity): Layer 1 every canonical page exists AND is in `nav:`, keyed on **English slugs** never localized titles; Layer 2 optional `docs/.docs-skeleton.yaml` (required_pages override + per-family headings, repo-owned labels). Parses mkdocs.yml via a SafeLoader subclass (tolerates `!!python/name:` tags, never constructs objects). Verified: fresh scaffold passes, dropping a nav entry → exit 1; CI harness green (149 tests).
- [x] #52 — **DONE (branch `feat/project-memory-cluster-52-75`, PR #96)** — the lazy pattern was already followed (thin tier roots, nested leaf `CLAUDE.md` under src/docs/tests/_internal, **zero** `@`-imports), so this documents the standing rule so it isn't regressed: a **Project memory** section in all 5 tier root `CLAUDE.md` — thin root + lazy leaves via nested `CLAUDE.md` / `paths:`-scoped rules, **never** a `@.claude/*` table (`@path` is an eager session-start import); plus the config-beats-prose corollary. Verified: DDD 144 tests + lib 6 pass, make lint clean.
- [x] #75 — **DONE (same branch, PR #96)** — consolidated lib's `_internal/ports/` **under** `_internal/config/ports/` (config/ = home of all private structural declarations). Scaffold: `mkdir` path, the `ports.` → `config.ports.` import rewrite, `copy_internal_ports` targets `config/ports/`, and it no longer copies a separate `ports/CLAUDE.md`. Folded `ports_CLAUDE.md` into `config_CLAUDE.md` (now a 3-sub-package map — contracts + opt-in ports + opt-in schemas — with the **schema↔document vs FileContract↔flat-table** boundary); deleted `ports_CLAUDE.md`; updated the root `CLAUDE.md` layout tree. Verified on a fresh lib scaffold: ports import `<pkg>._internal.config.ports`, no stale top-level dir, single config/CLAUDE.md, harness green.

## PR / repo automation

- [x] #53 — **DONE (branch `feat/pr-automation-repo-settings-53-56`)** — `bin/enable_repo_rules.sh`: provisions the `pr-quality-gate` ruleset on `~DEFAULT_BRANCH`, idempotent **by name** (PUT if present / POST if not, never a blind POST). Rules: `pull_request` (**`required_approving_review_count: 0`** — any ≥1 locks a solo maintainer out, GitHub forbids self-approval — plus binding `required_review_thread_resolution`), `code_scanning` (CodeQL, high_or_higher / errors), `copilot_code_review` (**its own rule type**, not a `pull_request` param), `non_fast_forward`, `deletion`. Also sets the gate's prerequisites: CodeQL default setup, `allow_auto_merge` (**read back** — without it auto-merge silently no-ops), `delete_branch_on_merge`, `do-not-merge` label. ⚠️ **`REQUIRED_CHECKS` ships EMPTY on purpose** — a required check that never reports blocks every PR forever; populate from a real PR's check-run names. Wired into `make init` + `tasks.sh` with full parity. Verified: JSON builder validated on BOTH branches (empty → rule omitted; populated → contexts verbatim), shellcheck + `bash -n` clean, harness green (149 tests).
- [x] #54 — **DONE (branch `feat/pr-gate-cluster-54-60`)** — `bin/pr_gate.py` + `pr-gate.yaml`: classify **by changed PATH** (never diff size — the dangerous change is semantic), one sticky comment (hidden-marker upsert), **native** auto-merge (GraphQL `enablePullRequestAutoMerge`, not `PUT /merge` — bypasses nothing), consent **opt-OUT** (`do-not-merge`). Default-deny: `other` (unmatched path) never merges. Pure classifier unit-tested (31 tests). Polls to **terminal** state, not `!= pending` (freeze bug); matches CodeQL **`Analyze`**, not the umbrella.
- [x] #55 — **DONE (same branch)** — **user scoped this to "CodeQL + ruleset only, document the boundary"** (no external AI, no API-key secret), which collapses it into #53's script: CodeQL default setup is enabled by `enable_repo_rules.sh`, the `copilot_code_review` rule ships in the ruleset, and `docs/contributing.md` documents the **repo-config vs account-plan** boundary explicitly — every repo setting is scripted, but Copilot code review is **not** in Copilot Free, so the rule sits correctly configured and **inert** (silent, not erroring). Also documents the `user/copilot_billing` → 404 misdiagnosis trap. No separate PR needed.
- [x] #56 — **DONE (same branch)** — `bin/enable_security.sh` PUTs the three free toggles (private vulnerability reporting → Dependabot alerts → Dependabot **security** updates **last**, since it depends on alerts); `templates/common/SECURITY.md` (English — a researcher surface — with `${PROJECT_DISPLAY_NAME}`/`${REPOSITORY}` placeholders; GitHub auto-detects it, no API call); `templates/python-common/.github/dependabot.yml` with **`versioning-strategy: lockfile-only`** (refreshes the lock so CI tests ~what consumers install, never rewrites `pyproject` ranges, never trips the lock-sync guard), minor+patch grouped, majors solo, `pandas` major ignored, plus the `github-actions` ecosystem. Both new assets are GitHub-remote-only. Verified: YAML parses, envsubst leaves no residual placeholders.
- [x] #57 — **DONE (same branch)** — `pr-gate.yaml` gains a `workflow_dispatch` **`backfill`** input that re-evaluates every open PR (a `pull_request`-driven gate never re-runs a PR that was open when the policy changed); documented in `contributing.md` as a post-policy-change step. NEVER `workflow_run` (fires only from the default branch → untestable on its own PR).
- [x] #58 — **DONE (same branch)** — `pr-reconcile.yaml`: closes `Closes #N` issues **and** deletes the head branch of merged PRs (a bot merge suppresses BOTH — same root cause). ⚠️ The `pull_request:[closed]` fast path is itself suppressed for a bot merge (measured), so the **scheduled daily sweep is the actual fix** (scheduled events are exempt from the GITHUB_TOKEN no-new-runs rule); no PAT.
- [x] #59 — **DONE (same branch)** — the `XL` size veto is **waived for a lockfile-only diff** (`is_lockfile_only`; `LOCKFILE` named once — both a `deps` trigger and the exemption). Narrow, not class-wide (a hand-edited `pyproject.toml` sibling stays vetoed). **Also fixed the companion trap I shipped in PR #99**: removed `labels:` from `dependabot.yml` — the PR gate owns labels, and a declared label absent from the repo makes Dependabot error on every PR it opens.
- [x] #60 — **DONE (same branch)** — `bin/check_backlog_ledger.py` (pre-commit + CI, gate parity): a branch touching `src/`/ci with no `docs/backlog/<kebab>_YYYYMMDD_HHMMSS.md` ledger fails. Reuses `pr_gate.classify_risk` **per path** (set-membership, not the collapsed most-dangerous class — the trap that would let a bin/+tests/ branch escape); diffs the **index** vs merge-base (staged ledger counts); no-op off a feature branch. CI checkout gets `fetch-depth: 0`. Unit + git-plumbing integration verified.

## Release / coverage

**Cluster DONE (branch `feat/release-coverage-cluster-61-62`)** — both shipped in one PR.
- [x] #61 — `fix`: coverage badge offline. `genbadge coverage --local` in **all four** places
      (gate parity): `.github/workflows/tests.yaml`, `Makefile` (`test_cov`), `tasks.sh`
      (`test_cov`), and the `coverage-badge` pre-commit hook. Rationale comment on the CI path.
      **Verified:** ran the exact shipped command in a scaffolded tree — exit 0, valid SVG,
      **0 `shields.io` references** (fully offline).
- [x] #62 — `fix`: a rehearsal only rehearses the steps it shares. Fixed the `files: dist/*`
      landmine in `lib-minimal/.github/workflows/release-pypi.yaml` → `dist/*.whl` +
      `dist/*.tar.gz` (the scaffold tracks a **0-byte `dist/.keep`**, and GitHub's API rejects a
      0-byte asset — aborting `action-gh-release` mid-way leaves a **draft** release, for which
      GitHub creates **no tag**, poisoning tag-derived versioning). Added a comment marking the
      GitHub-Release step as **prod-only / never rehearsed** by `release-test-pypi.yaml`.

## Ingestion / data contracts

**Cluster COMPLETE — part 1 (#67–#68) via PR #91, part 2 (#63–#66) via PR #92 (squash `76cde27`,
merged 2026-07-20, CI 38/38 green).** Two process lessons captured from part 2, both worth
honouring on the remaining clusters:
1. **Read `~/.claude/memory/lessons/README.md` BEFORE planning template work.** The store already
   held `drift-check-respects-subset-vs-full-column-contracts` + `drift-job-reuses-read-and-pins-explicit-wiring`
   (from filings-cvm) describing the very drift job #66 asked for. Skipping it shipped a
   false-positive defect (flagging unlisted source columns on *subset* contracts — ~122:1 cry-wolf
   in a real run) that had to be fixed before merge via `FileContract.bool_full_column`.
2. **Verify with `bash bin/ci/scaffold_lint_test.sh <skeleton>`, not ad-hoc `ruff check <files>`.**
   `make lint` short-circuits (ruff whole-tree → ruff format → mypy → codespell), so one ruff error
   means mypy/codespell never run. CI failed 4/6 scaffold jobs on a single `TID251` type-only
   import; lib-minimal passed and masked it (its scaffold rewrites the import path, so the
   literal-path ban no longer matches).

- [x] #63 — **DONE (branch `feat/ingestion-contracts-cluster-63-66`)** — shipped the provenance
      seam `utils/provenance.py` (`hash_artifact` I/O half + pure `stamp_provenance` +
      `resolve_package_version`), the six-column `FileContract.PROVENANCE_COLUMNS` + `output_columns`
      property, and the `bin/check_provenance.py` gate (wired into **both** `.pre-commit-config.yaml`
      and `tests.yaml`, gate-parity). The gate keys on the **call form** `read_table(` on purpose:
      `read_query` (own-DB read) is out of provenance scope, and a contract module that merely *names*
      `read_table` in prose (`example_source.py`) is a declaration, not a read — so it isn't
      false-flagged. `provenance.py` added to all 5 scaffold copy-lists; `test_provenance.py` (8 tests)
      auto-copies to the service tiers. Docs: standing decision in `src/config/CLAUDE.md` + rows in the
      tier `CLAUDE.md`. **Verified across all 3 layouts:** MVC-native (8 prov tests + both gates + ruff
      check/format clean), DDD-native (chassis.typing fallback, 14 tests, both gates), lib-minimal
      (import rewrite sound, gate green). **Negative control:** a reader calling `read_table(` without
      a stamp fails the gate (exit 1); adding the stamp passes (exit 0). ⚠️ Test-import note: uses the
      **bare `utils.`** prefix (like `test_logs_emitter`), not `src.utils.` — under pytest's
      `pythonpath = . src` the `src.` prefix loads a *second* module copy with distinct class
      identities, which beartype (correctly) rejects on the `FileContract` param.
- [x] #64 — **DONE (same branch)** — shipped `utils/sidecar_metadata.py` as a **generic seam** (user
      chose "generic seam + CVM reference"): `cvm_meta_url(base, key)` reference locator
      (`<base>/META/meta_<key>.txt`), `fetch_sidecar_text(url, path_raw, fn_download=download_file)`
      (persists to bronze + returns text, or `None` when absent — tolerant, never raises), and
      `parse_sidecar_metadata(text)` → `{field: {column: value}}` (header-driven, format-agnostic).
      Locator + download transport are injectable; CVM is the documented reference, not hard-coded.
      `sidecar_metadata` added to all 5 copy-lists; `test_sidecar_metadata.py` (5 tests) auto-copies
      to services. Docs: standing decision in `src/config/CLAUDE.md` + tier `CLAUDE.md` row.
      ⚠️ Correctness catch fixed in-flight: `Callable` must be a **runtime** import (not
      TYPE_CHECKING-only) — beartype resolves the `fn_download` hint at call time. **Verified** on
      fresh MVC + DDD scaffolds: seam + test ship, both gates green, 13 tests pass, ruff clean.
- [x] #65 — **DONE (same branch)** — doc-only convention appended to the contracts home
      `src/config/CLAUDE.md` ("Ground a contract's invariants in the real artifact"): measure the
      invariant on a downloaded artifact before asserting it; write the measured range into the
      docstring where the data refutes it (so the absent check reads as a decision); corollary —
      upstream class names lie, confirm the artifact from its URL. Ships to all service tiers via
      the single `config/CLAUDE.md` source. No code/test (pure guidance).
- [x] #66 — **DONE (same branch)** — **user chose FULL scope** (convention + fixture helper +
      drift-job workflow, overriding the lazy "defer the workflow" default). Shipped: the "pin every
      contract to a source-published oracle" standing decision in `src/config/CLAUDE.md` (two-layer
      table: offline PR-time fixture gates; online weekly drift job **never** gates); `bin/pin_contract_oracle.py`
      (extracts a real artifact's header → `tuple_required` / header-only PII-safe fixture, generated
      not transcribed); a copyable worked example `tests/unit/test_contract_oracle_example.py` +
      `tests/fixtures/example_source__header.csv` asserting `EXAMPLE_SOURCE.tuple_required == oracle`;
      the registry `src/config/contract_oracles.yaml` (empty by default → driver self-skips);
      `bin/check_contract_drift.py` (re-fetches each source, diffs the live header, **always exits 0** —
      reporter not gate); and `.github/workflows/contract_drift.yaml` (weekly + dispatch, **never**
      PR/push, opens/updates ONE deduplicated `contract-drift` issue via `--body-file`, `continue-on-error`).
      pin/driver ship via wholesale `bin/` copy; registry + workflow + example test/fixture wired into the
      **4 service tiers** (not lib — the ingestion tier). **Verified** fresh MVC: all artifacts land online
      path wired (offline correctly omits the workflow like tests.yaml), driver self-skips (exit 0, empty
      report) and detects injected drift (added/removed cols, no false positive, graceful unknown key),
      workflow YAML valid (triggers schedule+dispatch only), example test passes + ruff clean, 135 unit
      tests pass, both gates green.
- [x] #67 — **DONE (branch `fix/ingestion-cluster-67-68`)** — `apply_dtypes` normalises a `"str"`
      declaration to the nullable `"string"` dtype via a `_resolve_text_dtypes` helper + `_DTYPE_TEXT`
      constant. **Verified on BOTH pandas majors** (the lesson's own corollary — a green suite on one
      proves nothing about the other): reproduced the raw bug on pandas 2.3.3
      (`astype("str")` → `['A', 'nan']`, `isna [False, False]`), then 7 tests pass on 2.3.3 and 135 on
      3.0.3. **Mutation-tested**: reverting the normalisation makes the new test fail on pandas 2.
- [x] #68 — **DONE (same branch)** — `zip_extractor.find_member(list_members, str_name)` matches the
      **exact** file name and raises `ValueError` naming the member + listing what was available.
      Test writes the archive so a `startswith` scan would hit the WRONG member first
      (`lamina_fi_carteira_202601.csv` before `lamina_fi_202601.csv`).

## Lint / hooks / tests / misc

**Cluster DONE (PR #87, squash `4d15dfd`)** — all 6 shipped in one PR.
Verified across all structural tiers (MVC 132 / DDD 127 / lib 6 unit tests pass **with the
network guard active**, `make lint` clean, trees unchanged; guard fires on a real connection
via negative control):
- [x] #69 — `refactor`: prefer expression form; never suppress a formatter-enforced rule.
      `ruff.toml` block comment on why **E701 stays enabled** (suppressing it is dead config —
      `ruff format` re-expands the statement) + a code-style note in `python-common/CLAUDE.md`.
- [x] #70 — `chore`: pre-seed `.codespellrc` `ignore-words-list` with a generous PT-BR seed
      (~40 words) under the `# LOCALE EXTENSION POINT`; documented "extend, never `skip` a file".
- [x] #71 — `chore`: `.gitignore` covers `.claude/settings.local.json` + `.tmp.*` — both
      `python-common` and `ts-common` tiers.
- [x] #72 — `chore`: `exclude: ^tests/fixtures/` on `trailing-whitespace` + `end-of-file-fixer`
      in `.pre-commit-config.yaml` (verbatim oracle bytes must never be normalised).
- [x] #73 — `test`: `tests/conftest.py` autouse **network block** (swaps the connection
      primitives to raise `NetworkAccessError`; `@pytest.mark.allow_network` opt-out registered in
      `pytest.ini`). ⚠️ Scope fix found in verification: block only the **connection** primitives,
      NOT `getaddrinfo` — offline SSRF/address classification legitimately resolves (the shipped
      `test_download_rejects_loopback_host` proved it). Wired into all 5 scaffolds.
- [x] #74 — `test`: `tests/unit/test_family_convention_example.py` — a self-contained worked
      example of the introspective-`__all__` convention test (discover the family, meta-test the
      discovery, assert per member). Wired into all 5 scaffolds; doc note in `python-common/CLAUDE.md`.

## Notes

- Earlier store lessons (origin ≤ 2026-07-08) are treated as already backported per the
  mirror; if any turns out to be a false-done, add it here as a new box.
- Board: https://github.com/users/guilhermegor/projects/8

---

## ✅ Completed 2026-07-20 — kept as a record

**The entire backport wave (#48–#75) is shipped and merged to `main`.** All 28 lessons backported across these PRs:

- Priority: #76 (PR #78), #77 (#81), #82 (#86), #48 (#84), #83 (#85)
- Lint/hooks/tests #69–74 (PR #87); Release/coverage #61–62 (#88)
- Ingestion part 1 #67–68 (PR #91); part 2 / data-contracts #63–66 (#92)
- Docs/site #49–51 (PR #95), #52/#75 (#96); superseded-note (#98)
- PR-automation part 1 #53/#55/#56 (PR #99); part 2 #54/#57–#60 (#100)

Per the keep-completed-backlogs rule, this file is retained as the team-reviewable record of what was done and why. Do NOT delete it.

### Follow-up shipped after the wave

- **#97 (PR #103)** — `codespell` now skips the git-ignored `*-lessons.md` mirrors in both
  `.codespellrc` files. ⚠️ Uses the **basename** glob: the issue's `docs/*-lessons.md` is
  invocation-dependent and silently fails under `codespell .` (how `make lint`/CI run it).
