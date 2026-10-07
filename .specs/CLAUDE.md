# CLAUDE.md — .specs/

This file guides Claude Code (and any other agent) when reading or writing inside
`.specs/` — the repo-root home for feature design specs, implementation plans, work
trackers, and the local lessons mirror. It exists so `s:brainstorming` /
`s:writing-plans` (and any tool following the same "does the project have a `.specs/`
root?" convention) land their output here instead of `docs/`, which is solely for
published documentation.

## Layout

```
.specs/
├── CLAUDE.md          # this file
├── features/
│   └── <feature-name>/
│       ├── design.md  # s:brainstorming output
│       ├── plan.md    # s:writing-plans output (optional — not every design reaches a plan)
│       ├── tasks.md   # the feature's work tracker (optional — see "Trackers" below)
│       └── pr.md      # the PR body (optional); pr-<N>-<slug>.md when a feature has several
├── backlog/
│   └── <kebab-topic>_YYYYMMDD_HHMMSS.md   # tracker for an effort spanning no single feature
└── _lessons/           # local mirror of the machine-global lessons store; git-ignored
                        # (see .gitignore), never a source of truth on its own
```

## Rules

- `<feature-name>` is kebab-case and matches the feature the spec/plan is about —
  not a date, not an issue number.
- A `features/<name>/` directory must contain at least one of `design.md`, `plan.md`
  or `tasks.md`. An empty feature directory is a structure error.
- Nothing else lives directly under `.specs/` besides `CLAUDE.md`, `features/`,
  `backlog/`, and `_lessons/` — no stray top-level notes. If it doesn't fit
  `features/<name>/`, it belongs in `backlog/` (work spanning no single feature) or in
  `docs/` itself (published content), not loose at the root.
- `backlog/` is flat and every file in it is named `<kebab-topic>_YYYYMMDD_HHMMSS.md`,
  the repo's output-file convention. The timestamp is set at creation and never renamed.
- `_lessons/` is populated locally (machine-side tooling), never hand-authored, and
  is git-ignored — do not commit files under it, and the structure guard does not
  require it to exist or be non-empty.
- `features/` splits on **lifecycle, not change type**. A feature directory named after a
  type (`bugfix/`, `chore/`, `feat/`, `fix/`, `docs/`, `refactor/`, …) is rejected: the type
  is already recorded in the branch name and the Conventional-Commit prefix, and a third
  copy in a path is a third thing to keep in sync (dotfiles-dev#442). A name that merely
  contains one (`bugfix-triage`) is a feature and passes.
- `pr.md` is the PR body; a feature with several PRs uses `pr-<N>-<kebab-slug>.md`, where
  `<N>` is an ordinal inside the feature, **not** the PR number — the body is written before
  the number exists, so the number goes in a header line inside the file. Both are
  recognized but never sufficient: a feature still needs `design.md`, `plan.md` or
  `tasks.md`. Any other file named `pr…md` (`pr1.md`, `pr_draft.md`, `PR.md`) is a structure error.
- `bin/ci/check_specs_structure.sh` enforces every rule above except where a rule is marked
  advisory. It runs in the root pre-commit hook and `scaffold_checks.yml` CI, same
  one-implementation pattern as every other gate in this repo (see the root `CLAUDE.md`),
  and takes `--root <dir>` so any tree can be checked by the same script (it is not copied into scaffolds today).

## Trackers

Any multi-step effort gets a tracker — see the root `CLAUDE.md` → "Backlog
discipline" for when one is mandatory. It is `features/<name>/tasks.md` when the work
maps to one feature, `backlog/<kebab-topic>_YYYYMMDD_HHMMSS.md` when it does not.

Status markers:

| Marker | Meaning |
|--------|---------|
| `- [ ]` | to-do |
| `- [~] <type>/<name>` | in progress on that branch |
| `- [x]` | done |

⚠️ `[~]` carries the **branch**, never an agent id: agent ids die with the session, so
"doing" without "by whom" re-creates the collision the tracker exists to expose. The gate
checks the vocabulary in `features/<name>/tasks.md` — any task line (`- [?]`, `* [?]`)
outside a code fence that is not `[ ]`, `[~] <branch>` or `[x]` fails, and a `[~]` not followed
by a `<type>/<name>` branch fails. It cannot check that the branch exists (advisory).
⚠️ A marker is a claim, not evidence — an `[x]` with no merged PR behind it is
blueprintx#509's failure in a cheaper file.

A completed tracker is **never deleted**; tick the last box, add a short
"Completed — kept as a record" note, and leave it as the permanent record.

## History

`docs/superpowers/specs/` and `docs/superpowers/plans/` were the pre-`.specs/`
landing spot (excluded from the MkDocs build via `exclude_docs`). Their contents
were migrated into `features/<name>/{design.md,plan.md}` when `.specs/` was
introduced (blueprintx#447); new spec/plan output goes directly here.

`docs/backlog/` was the pre-`.specs/backlog/` home for work trackers, hidden from the
published site by the same `exclude_docs` mechanism. Its 45 records moved here intact
in blueprintx#575 — `docs/` is for published documentation, and excluding a directory
from the build was camouflage for that boundary violation rather than a fix.
