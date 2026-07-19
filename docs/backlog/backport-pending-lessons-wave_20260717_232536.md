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

3. **[x] #82 — DONE (branch `feat/82-typing-policy-seam`).** Externalised the beartype typing
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
- [ ] #49 — `feat`: scaffold placeholder logo + landing image
- [ ] #50 — `docs`: ship `docs/api/` as a directory from day one
- [ ] #51 — `feat`: docs-skeleton gate, language-neutral (English slugs + nav)
- [ ] #52 — `docs`: layered project memory — lazy, not eager (`@path` is eager)
- [ ] #75 — `docs`: internal `CLAUDE.md` maps ports + schemas + layout under `config/`

## PR / repo automation

- [ ] #53 — `feat`: PR quality-gate ruleset programmatically (`copilot_code_review` rule)
- [ ] #54 — `feat`: PR-gate auto-merge by changed path, never diff size
- [ ] #55 — `feat`: free AI + CodeQL PR review (CodeQL default setup via `make init`)
- [ ] #56 — `feat`: `SECURITY.md` + `bin/enable_security.sh` + `dependabot.yml`
- [ ] #57 — `fix`: PR-event gate freezes PRs open across a policy change (re-trigger open PRs)
- [ ] #58 — `fix`: auto-merged PRs don't close their linked issues (closed-event job)
- [ ] #59 — `fix`: size heuristics measure nothing on generated artifacts (exempt gen-only diffs)
- [ ] #60 — `feat`: enforce work-ledger with a diff-based path gate

## Release / coverage

- [ ] #61 — `fix`: coverage badge offline — never gate release on an external fetch
- [ ] #62 — `fix`: a rehearsal only rehearses the steps it shares (diff the two workflows)

## Ingestion / data contracts

- [ ] #63 — `feat`: ingestion stamps `url` + `updated_at` provenance
- [ ] #64 — `feat`: ingestion imports sidecar META metadata when available
- [ ] #65 — `fix`: ground invariants on the real artifact, not just schema
- [ ] #66 — `fix`: pin contracts to a source-published oracle (fixture + drift job)
- [ ] #67 — `fix`: `apply_dtypes` maps `"str"`→`"string"` (NA-safe below pandas 3)
- [ ] #68 — `fix`: `zip_extractor.find_member` — exact name, never prefix

## Lint / hooks / tests / misc

- [ ] #69 — `refactor`: prefer expression form; never suppress a formatter-enforced rule
- [ ] #70 — `chore`: pre-seed `.codespellrc` with the docs-locale vocabulary
- [ ] #71 — `chore`: `.gitignore` covers `.claude/settings.local.json` + `.tmp.*`
- [ ] #72 — `chore`: exclude `tests/fixtures/` from whitespace/EOF pre-commit hooks
- [ ] #73 — `test`: block network in tests with an autouse conftest guard
- [ ] #74 — `test`: enforce conventions with an introspective `__all__` test

## Notes

- Earlier store lessons (origin ≤ 2026-07-08) are treated as already backported per the
  mirror; if any turns out to be a false-done, add it here as a new box.
- Board: https://github.com/users/guilhermegor/projects/8
