# Lessons-audit wave 2 — issues #143–#153

Created 2026-08-09. Second pass over the lessons corpus, scoped to everything written or
amended **after** the first wave (`lessons-audit-wave_20260805_083429.md`, issues #113–#130).

## How this set was derived

| Source | Size | Method |
|---|---|---|
| `~/.claude/memory/lessons/` | 212 files (was 193) | `find -newermt 2026-08-05` → 32 touched files |
| Existing issues | 60 (open + closed) | every lesson slug matched against every issue title+body |
| `templates/` tree | — | substance probe on each candidate before filing |

The first wave's two-stage audit (slug diff, then `Scaffold into:` target resolution) was
re-validated and holds — **no gap was found in the pre-2026-08-05 corpus**. A naive slug scan
reports 126 "untraced" lessons, but that is an artefact: the pre-wave issues were filed by
**title**, not slug. Every one spot-checked resolved to a closed or open issue.

The new issues therefore all trace to lessons captured in the **four days** since.

## Three confirmed shipped defects (probed, not inferred)

| File | Line | Defect |
|---|---|---|
| `templates/python-common/src/utils/tabular_reader.py` | 316-317 | `.astype(str)` **and** `series_valid.any()` on a possibly-empty series |
| `templates/python-common/bin/check_contract_drift.py` | 125, 192 | unreachable source returns `[]`, job prints *"No contract drift — every contract still matches its source"* |
| `templates/python-common/bin/pr_gate.py` | 445 | `enablePullRequestAutoMerge` result discarded → a GraphQL 200-with-`errors` refusal is a silent no-op |

## Issues opened

### Confirmed shipped defects
- [ ] **#143** `fix(python-common)` — `tabular_reader` identifier check: `any()` on an empty series + non-NA-safe `astype(str)`
- [ ] **#144** `fix(python-common)` — the drift job reports its own blindness as "no drift" (+ timeout, subset-contract noise)
- [ ] **#145** `fix(python-common)` — `pr_gate` hardening (4 lessons): discarded GraphQL refusal, merge handover, required-check population, thread gate

### New gates
- [ ] **#146** `feat(python-common)` — pre-push guard: a non-empty index at push time means a rejected commit
- [ ] **#149** `feat(python-common)` — code-derived coverage floor + audit a proxy-seeded backlog against the publisher index (2 lessons)

### Ingestion seams
- [ ] **#147** `feat(python-common)` — reader robustness: positional width, untrusted field names, real fixture envelope (3 lessons)
- [ ] **#148** `feat(python-common)` — per-regime adapters for a mid-series schema change
- [ ] **#150** `feat(python-common)` — cache a daily-stable vendor download inside the seam

### Tier-specific / docs
- [ ] **#151** `fix(templates)` — a documented graceful degradation needs a path from every failure (`mvc-*`)
- [ ] **#152** `docs(templates)` — `tests/CLAUDE.md`: negative-control and proof discipline (4 lessons)

### Security scanning (follow-up question, not from a lesson)
- [ ] **#153** `feat(python-common)` — `enable_security.sh`: add `secret_scanning` +
      `secret_scanning_push_protection`

### Edits to existing issues
- [x] **#119** commented — add `check_query_layout.py`, the enforcement half
      (`gate-a-convention-only-the-resolver-enforces`, captured after #119 was filed)
- [x] **#137** closed as a byte-identical duplicate of **#138**
- [x] **#129** re-scoped and retitled — from "scaffold `.coderabbit.yaml`" to **the agnostic
      PR-gate reviewer/scanner topology**: CodeRabbit (review) **+ GitGuardian (secrets)**, wired
      through the same seam as #145's bot roster

## Decisions recorded

- **Verification lessons route to BOTH stores.** The first wave sent this class to
  `dotfiles-dev#112` ("Proving a claim" in `rules/common.md`). User decision this session: the
  four newer ones **also** get a BlueprintX home, as `tests/CLAUDE.md` content (#152), because
  the harness rule reaches *this* machine while the leaf doc reaches every *generated project*.
  `prove-a-refactored-gate-still-fires` stays partly in #111.
- **Grouping = one issue per shipped surface**, not one per lesson — 13 lessons → 10 issues.
- **Starting column = Backlog** for all eleven, matching the #113–#130 wave (these are backports
  with real design work left, not pull-ready tasks).
- **CodeRabbit + GitGuardian both live in #129**, as two participants in one *provider-agnostic*
  topology — CodeRabbit produces review threads, GitGuardian produces a secrets check. Pairing
  them in one issue is deliberate: wired separately, the second one added hardcodes a vendor into
  a business rule. The contract is #145's — **gate on FINDINGS, never on PARTICIPATION**, vendor
  names only inside the bot roster, and no new required context without a measured population.
- **#153 is a different layer, not an alternative.** Push protection rejects a secret **at push
  time** with no PR involved; GitGuardian reports on the **PR**. A secret reaching a PR already
  survived push protection, so the PR-side finding is the second line. Ship both. An initial
  "GitGuardian evaluated, deferred" framing in #153 was **withdrawn** by comment.
- **Two premises to verify before building #129**, both recorded on the issue: (a) `templates/`
  ships no CodeRabbit config and filings-cvm has no `.coderabbit.yaml` either — what makes its
  threads binding is the ruleset's `required_review_thread_resolution` (measured: blocked PRs
  #207/#210), not a config file; (b) the docs never state the CodeRabbit **CLI** reads
  `.coderabbit.yaml` (`/cli/configuration` 404s), and the whole offline half rests on it.
  `ggshield` is a real local CLI, so the offline story may be stronger on the GitGuardian side —
  evaluate on merits, not by analogy.

## Already covered — checked, not filed

`npm-trusted-publishing-*` (#135), `blocklist-cannot-gate-unknown-imports` (#138/#139/#140),
`gate-the-code-english-half-*` (#141), the six offline-git lessons (#142),
`venv-cache-guard-*` (#111), `xml-reader-seam` (#117), `retry-backoff-download-seam` (#116),
`pip-fallback-needs-offline-wheelhouse` (#127), `enumerate-a-source-via-its-index-api-not-html`
(#128), `corporate-ca-must-union-not-replace` (#114),
`config-key-renamed-silently-changes-env-lookup` (#121),
`branch-work-ledger-in-docs-backlog` (#60, closed),
`pr-event-gate-freezes-*` original half (#57, closed — the 2026-08-09 amendment is in #145).

## Notes for the next audit

- **Stamp the issue number in the lesson file.** Only 7 of the 32 recently-touched lessons carry
  an `**Issue:** blueprintx#N` line; the rest forced a title-by-title reconciliation. Every slug
  filed in this wave appears verbatim in its issue body, so a mechanical `slug ∈ issue.body` scan
  now resolves them — keep that property.
- The naive slug scan's 126 "untraced" hits are **mostly false positives** from title-filed
  pre-wave issues. Do not re-derive a wave from that number alone.
