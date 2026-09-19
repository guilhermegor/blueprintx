# **SonarQube Evaluation — Decision Record**

Audited against what BlueprintX's scaffolds already run in CI, to decide whether SonarQube
should be adopted. **Decision: do not adopt.** Tracked as
[issue #428](https://github.com/guilhermegor/blueprintx/issues/428).

> **See also:** [Contributing](contributing.md) · [Troubleshooting](troubleshooting.md).

---

## What SonarQube measures

Per SonarQube's own documentation ([Rules and issue types][rules-doc]), it reports four issue
types plus two categories of aggregate metrics:

- **Bug** — "code that is demonstrably wrong, or more likely wrong than not."
- **Vulnerability** — "code that could be exploited by an attacker."
- **Security Hotspot** — "code that is security-sensitive," flagged for human review rather
  than treated as a definite finding.
- **Code Smell** — "neither a bug nor a vulnerability," maintainability-shaped issues.
- **Duplication metrics** — duplicated-lines density, duplicated blocks/files (does not cover
  Terraform-like IaC or CSS).
- **Complexity metrics** — cyclomatic complexity ("number of paths through code") and cognitive
  complexity ("how hard control flow is to understand"), reported per-file/per-project, not
  gated by default.
- **Maintainability rating / technical debt ratio** ([Metric definitions][metrics-doc]) — an
  aggregate letter grade (A–E) computed as `technical debt / (cost per line × LOC)`, a
  project-wide report rather than a line-level finding.

## Coverage map — category by category

| SonarQube category | Already covered here | By what |
|---|---|---|
| Bug / Code Smell (general lint) | **Yes** | `ruff` — 19 rule families enabled in `templates/python-common/ruff.toml` (`UP`, `E`, `F`, `ANN`, `B`, `SIM`, `I`, `AIR`, `ERA`, `S`, `PD`, `D`, `TID`, `W`, `PL`, `PT`, `RET`, `A`, `N`), plus ESLint (`eslint.config.js`/`.mjs`) with `@eslint/js` + `typescript-eslint` recommended sets, React/hooks/a11y/import/jest/boundaries plugins in the TS skeletons |
| Vulnerability (SAST) | **Partial** | GitHub CodeQL default setup is enabled on this repo (`actions`, `javascript`, `javascript-typescript`, `python`, `ruby`, `typescript` — confirmed via `gh api .../code-scanning/default-setup`); `ruff`'s `S` (flake8-bandit) rule family also catches a subset (SQL built by string concat, `eval`, weak hashes, etc.) |
| Security Hotspot / secrets | **Yes** | `gitleaks` in `.github/workflows/secret_scan.yml` — scans full repo history (root + `templates/`). ⚠️ The issue's own table names GitGuardian/`ggshield`; the actual tool wired in this repo is `gitleaks`, verified by reading the workflow — corrected here rather than restated |
| Vulnerable dependencies | **Yes** | Dependabot: security updates are a repo-wide toggle already enabled independent of any config file; `.github/dependabot.yml` additionally adds routine, non-urgent version-update PRs (blueprintx#471) |
| Cyclomatic complexity | **Yes** | `templates/python-common/bin/check_complexity.sh` — per-tree ceilings (`tests/`=1, `src/`=2, `bin/`=8), measured and justified per blueprintx#425, built on ruff's own `C901` rather than a second implementation |
| Cognitive complexity | **No** | Nothing here measures this distinct metric today — see Gap below |
| Code duplication (CPD) | **No** | Tracked separately in blueprintx#305 (`jscpd`), open, not this issue's job to close |
| Test coverage | **Partial** | `check_coverage_floor.py` enforces a line-coverage floor per skeleton; **branch coverage** is explicitly not yet measured — tracked in blueprintx#427, open |
| Maintainability rating / aggregate debt score | **No** | No aggregate report exists or is planned; see Gap below |
| Function length | **Yes** | `check_function_length.py`, one implementation, run on both BlueprintX's own tree and every generated project |
| Direct-dependency hygiene | **Yes** | `lint_deps.sh` (deptry) — scaffold-side only, see root `CLAUDE.md` for why it can't run on BlueprintX itself |
| Additional gates SonarQube has no equivalent for | **Yes, this repo has more** | `check_layer_imports.py` (DDD boundary enforcement), `check_sql_guards.py`, `check_rmw_race.py`, `check_typing.py`, `check_dtypes.py`, `check_assertion_weakening.py`, `check_docstrings.py`, `check_contract_drift.py`, `check_provenance.py`, `check_fixture_scope.py`, `check_comment_budget.py`/`check_comment_language.py`, `check_all_exports.py`, `check_docs_sections.py`/`check_docs_code_refs.py`, `check_backlog_ledger.py`, `check_gate_integrity.py`, `check_unix_filenames.sh`, `check_clean_index.sh` — architectural and repo-hygiene rules no generic SAST tool expresses |
| Code review / PR gate | **Yes** | CodeRabbit + GitHub's built-in Copilot reviewer, tracked by `.review-bots.yaml` and enforced by `check_review_threads.py` |
| CI workflow correctness | **Yes** | `actionlint` (`bin/ci/check_actions.sh`), plus `check_job_timeouts` |
| Spelling | **Yes** | `codespell`, synced root ↔ `templates/python-common/` by `check_codespell_sync.sh` |

`ruff`'s 19 rule families plus the 20+ purpose-built `check_*` gates in
`templates/python-common/bin/` cover materially more ground than SonarQube's default rule set —
most of those gates enforce architectural invariants (hexagonal layer boundaries, SQL-guard
patterns, read-modify-write races, provenance, DDD contract drift) that no generic static
analyzer expresses, because they are specific to this scaffold's own design, not general-purpose
code smells.

## Genuine gaps found

Two things SonarQube would report that nothing here measures today:

1. **Cognitive complexity.** `check_complexity.sh` measures cyclomatic complexity (path count)
   via ruff's `C901`; SonarQube's cognitive-complexity metric (control-flow *readability*, which
   penalizes nesting and boolean chaining differently from raw branch count) has no equivalent
   gate here. Real gap, but narrow — cyclomatic complexity already bounds the same functions,
   and blueprintx#425 is the open venue to decide whether a second metric earns its keep.
2. **Aggregate maintainability rating / technical debt ratio.** No project-wide report exists.
   This repo has already decided against this shape of output once — see "Contradicts a rule
   already written" below — so this is a known, deliberate absence, not an oversight.

Neither gap changes the recommendation: both are narrow, already tracked or already decided, and
neither is blocked on adopting a new tool.

## Why not adopt — in order of weight

**1. The owner's environment is the adverse case, and it's on record.** Project memory records
a corporate environment that forbids `pyenv` and sits behind a TLS-inspecting proxy. Per
SonarQube's own install docs ([Community Build setup][cb-setup]), the Community Build is
**self-hosted only** — Docker or a manually-run Java 21 server, no SaaS option. SonarQube Cloud
is SaaS, which means sending code through a proxy that inspects TLS. A scaffold whose quality
gate depends on a service that doesn't come up in the target environment is worse than no gate.

**2. The free edition doesn't do what a PR gate needs.** Per SonarQube's own documentation
([Pull request analysis][pr-doc]), PR decoration and branch analysis are **Developer Edition and
above** — not available in the Community Build. Pricing ([sonarsource.com/plans-and-pricing][pricing]):
SonarQube Cloud's free tier covers private projects up to 50k LOC; its paid Team plan starts at
$34/month for up to 100k LOC; SonarQube Server's Developer/Enterprise/Data Center editions are
priced per instance per year by LOC, with no public figure published. The value this issue was
evaluating — a PR-level gate — sits behind a Developer-Edition-or-Cloud-Team-tier paywall.

**3. Contradicts a rule already written.** This repo declined `pylint` and `radon` because
`ruff` already answers the same questions (see root `CLAUDE.md`, cyclomatic-complexity gate
section). SonarQube is the same decision at larger scale, and it adds a specific failure mode
this repo has already named as the worst kind: **two gates disagreeing about the same line**,
with no declared tie-breaker.

## Recommendation

**Do not adopt.** This document is the record — kept so the proposal does not resurface without
new numbers. Reopen if either becomes true:

- Duplication becomes a measured problem and `jscpd` (blueprintx#305) doesn't cover it, or
- The project grows a team, at which point an aggregate maintainability report starts paying for
  itself.

If adopted later anyway, as an opt-in `make new` menu item (like the webhook/storage/secret-scan
precedents): it should ship online-only (`apply_offline_mode` has no server or token to talk to),
and its config needs an explicit rule for who wins when SonarQube's Quality Gate disagrees with
`ruff` — without one, the next developer disables whichever is noisier.

## Related

- [blueprintx#305][gh-305] — `gitleaks`/`osv-scanner`/`jscpd`/`semgrep` gap analysis; the only
  category SonarQube would add (duplication) is already this issue's job, not a new one.
- [blueprintx#425][gh-425] — cyclomatic-complexity ceilings, measured; would also be the venue
  for evaluating cognitive complexity.
- [blueprintx#427][gh-427] — branch coverage, the other metric SonarQube would report.

[rules-doc]: https://docs.sonarsource.com/sonarqube-server/latest/user-guide/rules/
[metrics-doc]: https://docs.sonarsource.com/sonarqube-server/latest/user-guide/metric-definitions/
[cb-setup]: https://docs.sonarsource.com/sonarqube-community-build/try-out-sonarqube/
[pr-doc]: https://docs.sonarsource.com/sonarqube-server/latest/analyzing-source-code/pull-request-analysis/
[pricing]: https://www.sonarsource.com/plans-and-pricing/
[gh-305]: https://github.com/guilhermegor/blueprintx/issues/305
[gh-425]: https://github.com/guilhermegor/blueprintx/issues/425
[gh-427]: https://github.com/guilhermegor/blueprintx/issues/427
