# CLAUDE.md — .specs/

This file guides Claude Code (and any other agent) when reading or writing inside
`.specs/` — the repo-root home for feature design specs, implementation plans, and
the local lessons mirror. It exists so `s:brainstorming` / `s:writing-plans` (and any
tool following the same "does the project have a `.specs/` root?" convention) land
their output here instead of `docs/`.

## Layout

```
.specs/
├── CLAUDE.md          # this file
├── features/
│   └── <feature-name>/
│       ├── design.md  # s:brainstorming output
│       └── plan.md    # s:writing-plans output (optional — not every design reaches a plan)
└── _lessons/           # local mirror of the machine-global lessons store; git-ignored
                        # (see .gitignore), never a source of truth on its own
```

## Rules

- `<feature-name>` is kebab-case and matches the feature the spec/plan is about —
  not a date, not an issue number.
- A `features/<name>/` directory must contain at least one of `design.md` or
  `plan.md`. An empty feature directory is a structure error.
- Nothing else lives directly under `.specs/` besides `CLAUDE.md`, `features/`, and
  `_lessons/` — no stray top-level notes. If it doesn't fit `features/<name>/`, it
  belongs in `docs/backlog/` (work-to-do) or `docs/` itself (published content), not
  here.
- `_lessons/` is populated locally (machine-side tooling), never hand-authored, and
  is git-ignored — do not commit files under it, and the structure guard does not
  require it to exist or be non-empty.
- `bin/ci/check_specs_structure.sh` enforces the layout rules above; it runs in both
  the root pre-commit hook and `scaffold_checks.yml` CI, same one-implementation
  pattern as every other gate in this repo (see the root `CLAUDE.md`).

## History

`docs/superpowers/specs/` and `docs/superpowers/plans/` were the pre-`.specs/`
landing spot (excluded from the MkDocs build via `exclude_docs`). Their contents
were migrated into `features/<name>/{design.md,plan.md}` when `.specs/` was
introduced (blueprintx#447); new spec/plan output goes directly here.
