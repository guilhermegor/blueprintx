# Lesson-store traceability — clearing the audit's debt

**Created:** 2026-08-16 · **Base:** `main` @ `b039a42`
**Origin:** the residual finding from the previous session's `/wrap-up` — *"170 lessons with no
issue/PR reference and 9 orphan issues"*, explicitly left for its own session.

---

## What the audit actually measures

`session_capture_audit.sh` → `emit_completeness()`:

- **Line 1 (lessons → issues):** a lesson counts as traced **only** if the file's text
  matches `blueprintx#[0-9]+`. Nothing else is recognized.
- **Line 2 (issues → lessons):** an open issue counts as *sourced* if some file in the store
  cites `blueprintx#<n>`.

## Two defects in the audit itself (found today)

- 🔴 **The denominator was truncated.** Line 2 calls `gh issue list --state open --json
  number` **without `--limit`**. `gh`'s default is **30**. The repo has **46** open issues, so
  the audit never looked at 16 of them — and the reported "9 orphans" is actually **12**. An
  audit that reports over a silent sample of the population is the exact failure half this
  store's lessons describe, occurring in the meter itself.
- 🔴 **There is no "delivered" marker.** A lesson already scaffolded counts as debt forever,
  because the only thing that clears it is citing a number. Measured consequence: of 243
  lessons, **73** cite a number and **170** do not — but that doesn't separate *pending* from
  *delivered-without-citation*. The lesson format **has no status field**; that's the root
  cause of nobody being able to answer "has this shipped yet?".

## The mechanical bridge

Matching 170 lessons by hand against 101 issues would be the error the
`backlog-seeded-from-a-proxy-inherits-its-blind-spot` lesson describes. The bridge exists:
**issue and PR bodies already name the lesson's slug in backticks**. A kebab-slug regex (≥3
segments, to avoid colliding with prose) over the 101 issues + 81 PRs resolves **82 of the 170
with zero judgment calls**.

**88** remain that no issue and no PR has ever named.

## Owner's decision (2026-08-16)

- Residue of 88: **verify and mark status, without opening new issues.** Do not inflate the
  backlog from 46 → ~80 before duskko's `make new`.
- **Fix the audit script** in dotfiles-dev (the version-controlled source), not just report on it.

---

## New format — `Status:` field

Goes right below `**Tier:**` in every lesson:

```markdown
- **Status:** delivered — blueprintx#182
- **Status:** tracked — blueprintx#128
- **Status:** queued — no issue filed
```

`delivered`/`tracked` satisfy the audit's current regex. `queued — no issue filed` does
**not** — on purpose: it is conscious debt, and the script's second fix is teaching it to
distinguish *undeclared* from *declared-pending*.

---

## Execution — ✅ COMPLETE

### 1. Mechanical bridge — 82 lessons

- [x] stamped: **53 `delivered`**, **29 `tracked`**, derived from the ref's own state
      (merged PR / closed issue → `delivered`; open issue → `tracked`)
- [x] negative control: `assert lessons` — the bridge **refuses to run** with an empty store,
      instead of reporting "everything traced"
- [x] samples cross-checked against the previous backlog: #125 and #130 are open issues from
      that cut and came out `tracked`, as they should

### 2. Residue — 88 lessons

- [x] **71 resolved from the repo's history**: `git log --diff-filter=A -- <target>` → the
      squash commit's `(#N)` suffix. 13 of them predate merge-by-PR and cite the SHA
      (`delivered — pre-PR (799db84)`) instead of a made-up number
- [x] **17 by judgment call**, each verified against the repo before the verdict
- [x] 🔴 **three method corrections along the way, all my own false negatives:**
      1. a `Scaffold into:` is usually written from the **generated project's** perspective
         (`bin/precommit.sh`), not from the blueprintx root — resolving against the root only
         reported 21 delivered lessons as pending; resolving against both bases dropped it to 9
      2. targets get renamed (`ci.yml` → `tests.yaml`) and re-hyphenated
         (`release_test_pypi.yaml` → `release-test-pypi.yaml`); without normalizing `-`/`_`,
         4 release lessons showed up as debt
      3. `docs/backlog/*.md` is a **third ledger** and already recorded `DONE` for lessons I was
         about to mark pending
- [x] ⚠️ none marked `delivered` because "the file exists" — every verdict names the commit
      or the check that backs it

### 3. Reverse direction — orphan issues

- [x] the audit said **9**; the real number was **12** (see the `--limit` defect above)
- [x] after stamping it dropped to **8**, and two of those **did** originate from a lesson,
      the lesson just never cited the number: **#120**
      (`ingestion-reader-persists-raw-artifact`) and **#175**
      (`gate-on-thread-content-not-on-resolver-identity`) — references added
- [x] the remaining **6** (#110, #132, #133, #134, #136, #164) are feature/ops work that
      genuinely does not originate from a lesson → logged in the **"Issues not born of a
      lesson"** section of the store's README, so they stop being re-triaged every session

### 4. Store README

- [x] `Status:` field documented with the table of 5 values
- [x] the two warnings that cost time this session written down as a rule: never mark
      `delivered` from a file's mere existence; resolve the path against both bases

### 5. Audit script (dotfiles-dev)

- [x] explicit `--limit 500`, plus a warning when the page **fills up** (at which point the
      count is a floor, not a total)
- [x] `Status:` recognized as a declaration; `queued` counted **separately** — it's the only
      number that is real debt
- [x] 4 new tests in `tests/session_capture_audit.bats` (a `Status` with no number counts as
      declared; `queued` counts separately; `advisory` does not count as queued; the `gh` stub
      records the argv and proves the `--limit`)
- [x] `shellcheck` clean; **`bats` is not installed on this machine**, so verification was
      running the script against the real repo, plus a negative control (a lesson with no
      `Status` → flagged; removed → back to zero)
- [x] deployed to `~/.claude/hooks/` (the live copy still had the bug)
- [ ] ⚠️ **not committed** — dotfiles-dev's only branch is `feat/pr-merge-threads-guard-126`,
      from PR #127 which is still open, and this fix doesn't belong on it

---

## Result

| | before | after |
|---|---|---|
| lessons with a recorded disposition | 73 / 243 (citation only) | **244 / 244** |
| real debt (`queued`) | unknown | **6** |
| orphan open issues | 9 reported (12 real) | **0** |

The denominator rises from 243 to 244 because the store **gained one lesson during this
session** — `scaffold-copy-excludes-build-artifacts`, from the collateral finding below. All
243 original lessons were stamped; the 244th was born already carrying `Status:`.

Final distribution: **156 delivered · 76 tracked · 6 queued · 4 advisory · 2 superseded** = 244.

The 6 `queued` are the honest debt left over, each with its absence evidence noted:
`confirm-the-spec-document-before-writing-the-reader` (no `config/contracts/CLAUDE.md`),
`config-reference-optional-override`, `instrument-before-the-gate-not-after-it`,
`codeql-default-setup-drops-a-pr-dispatch-deadlocking-merge`,
`recorded-browser-flow-is-data-not-code`, `scaffold-copy-excludes-build-artifacts`.

## Collateral finding — build output inside `templates/`

While verifying targets, two `__pycache__` entries pointed to modules **deleted on purpose**
(`mkdocs_hooks.py`, `yaml_reader.py`). There are **205 `.pyc` files** under `templates/`, and
the scaffolds do `cp -r templates/<tier>/src/.` **with no exclusion at all** — every generated
project is born with bytecode from another machine. Git never tracked these files, so
`git status` stays clean and the defect is invisible.

The expensive cost isn't the litter: an orphaned `.pyc` **outlives its `.py`** and makes
`grep -rl` answer that a module ships when it doesn't — which is what nearly produced two
wrong verdicts here. Lesson logged (`scaffold-copy-excludes-build-artifacts`, `queued`); **no
issue opened**, per the same decision governing this session.

**Complete — kept as a record.**
