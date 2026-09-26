# Lessons-audit wave — issues #113–#130

Created 2026-08-05. Tracks the backlog wave produced by a full audit of the lessons
corpus **and** the proving grounds' code.

## How this set was derived

| Source | Size | Method |
|---|---|---|
| `~/.claude/memory/lessons/` | 193 files | index ↔ files diff = 0 both directions |
| `~/.claude/memory/lessons-dotfiles/` | 45 files | scanned for misroutes |
| `~/.claude/tasks/lessons.md` | 805 lines | read in full (2 pages) |
| `docs/blueprintx-lessons.md` mirrors | 6 repos | 181 slugs; 1 orphan found |
| Proving-ground **code** | 4 repos | utils/bin module diff vs `templates/` |
| Existing issues | 42 | open + closed |

**Two-stage audit.** Stage 1 diffed lesson slugs against everything BlueprintX knows →
106 untraced. Stage 2 resolved each lesson's own `Scaffold into:` target against the real
tree, then substance-probed the 57 whose target was unresolvable.

Stage 1 alone was **not sufficient** — its "false positive" classification rested on ~13
spot checks. Stage 2 found one more real gap (#119) and corrected five false alarms.

## Issues opened

### Confirmed shipped defects
- [ ] **#113** `fix(scaffold)` — hyphenated project name generates an unimportable package
- [ ] **#114** `fix(python-common)` — `get_corporate_ca.sh` narrows the TLS trust store
- [ ] **#115** `fix(python-common)` — emoji in `bin/check_*.py` crash on Windows cp1252

### Strongest code-diff signal
- [ ] **#116** `refactor(python-common)` — split `utils/retry.py` into a `retry/` package (**4/4** proving grounds)

### Missing seams
- [ ] **#117** `feat(python-common)` — XML reader seam (`read_xml`) with attribute mapping — supersedes #112
- [ ] **#118** `feat(python-common)` — `utils/ms_office` + `excel_sheet_names` + `src/utils/CLAUDE.md`
- [ ] **#119** `feat(templates)` — `queries/<engine>/` + `load_query` + runtime guard for git-ignored config
- [ ] **#120** `feat(python-common)` — `raw_workspace` seam (bronze-layer retention)
- [ ] **#121** `feat(python-common)` — email orchestration half (`dispatch`/`sender`/`html_body`)
- [ ] **#122** `fix(python-common)` — public `to_absolute` at every foreign-process hand-off
- [ ] **#127** `feat(python-common)` — offline wheelhouse for the pip fallback

### Gates and process
- [ ] **#123** `fix(python-common)` — work-ledger gate permanently blocks every bot PR
- [ ] **#124** `docs(templates)` — `tests/CLAUDE.md` to the 4 tiers missing it
- [ ] **#125** `fix(python-common)` — pin `poetry-plugin-export` in the bootstrap installer
- [ ] **#126** `fix(python-common)` — codespell also lints the commit message
- [ ] **#128** `feat(python-common)` — ingestion contract discipline (8 lessons) + 2 gates
- [ ] **#130** `fix(templates)` — `docs/architecture.md` ships but is **ungated**

### Tooling
- [ ] **#129** `feat(templates)` — scaffold `.coderabbit.yaml` (online **+** offline); CodeRabbit **replaces** Copilot review

### Edits to existing issues
- [x] **#111** extended with `prove-a-refactored-gate-still-fires`
- [x] **#112** closed as superseded by #117

### Filed in dotfiles-dev (harness, not templates)
- [ ] **dotfiles-dev#112** — "Proving a claim" section in `rules/common.md` (6 misrouted verification lessons)

## Decisions recorded

- **#129 reviewer topology = option (a).** CodeRabbit replaces Copilot code review; drop
  `copilot_code_review` from the #53 ruleset. CodeQL stays (SAST, not a reviewer).
  > ⚠️ **SCOPE SUPERSEDED 2026-08-09 — see `lessons-audit-wave-2_20260809_143000.md`.** This
  > decision still holds *as far as it goes*, but #129 was **re-scoped and retitled** from
  > "scaffold `.coderabbit.yaml`" to **the provider-agnostic PR-gate reviewer/scanner
  > topology**: CodeRabbit (review threads) **plus GitGuardian (secrets check)**, both wired
  > through the same roster seam per #145. Do not build the CodeRabbit-only version from this
  > paragraph.
- **`.coderabbit.yaml` ships to online AND offline.** "Offline" here means *no GitHub
  remote*, not *no internet*; the CodeRabbit **CLI** reviews local git changes with no PR.
  ⚠️ Unverified: the docs never state the CLI reads the file (`/cli/configuration` 404s).
  > ⚠️ **STILL UNVERIFIED as of 2026-08-09**, and now known to be **load-bearing for the offline
  > tier only on the CodeRabbit side**. Measured since: BlueprintX itself runs CodeRabbit with
  > **no `.coderabbit.yaml` at all** (app defaults) — what makes its threads binding is the
  > ruleset's `required_review_thread_resolution`, not a config file. GitGuardian's `ggshield`
  > *is* a documented local CLI, so the offline story is stronger there; evaluate on merits,
  > never by analogy (#155).
- **#130 corrected the premise.** `docs/architecture.md` already ships in all 4 service
  tiers and is in nav — the defect is that it is absent from `_DEFAULT_REQUIRED_PAGES`
  and **no tier ships the `.docs-skeleton.yaml`** the gate's own comment names as the way
  to add it. `lib-minimal` stays exempt by design.

## Deliberately NOT filed

- **`scaffold-stamps-lessons-obligation`** — referenced in `perfil_mensal_cvm`'s mirror but
  **deliberately retracted**: `perfil_mensal_cvm/.claude/settings.local.json:260-261` holds
  approved `rm -f` + de-index commands. Filing it would re-litigate a settled decision. The
  stale mirror line is the leftover. **Open question: prune the line, or restore the lesson?**
- **`meta_parser.py` / `introspection.py`** (filings-cvm only) — flagged, not read. Candidates only.

## Corrections made during the audit

- Five ALL-MISSING verdicts were **present but relocated**: `optional/ports`,
  `optional/typing`, `src/config/contracts/`, per-tier `mkdocs.yml`, mvc `src/controller/`.
- `typing/` and `webhook/` looked absent on a `src/utils/`-only diff; they ship under
  `python-common/optional/`. Not gaps.
- Q4 resolved: the disproven `assert str(float(x)) != x` scale assertion is **not** shipped
  — the `str(float(` hits are unrelated `safe_str` NaN handling.
- A `queries/` token grep returned HIT while the directory held only `.gitkeep` → became #119.

## Notes

- The kanban hook parsed `113` out of an earlier branch name (`docs/lessons-audit-wave-113-130`)
  and moved #113's card to *In progress*. Branch renamed to `docs/lessons-audit-wave`; card
  reset to *Backlog*. Worth a dotfiles-dev issue if it recurs.
- All 18 issues confirmed on the blueprintx kanban in **Backlog**.
