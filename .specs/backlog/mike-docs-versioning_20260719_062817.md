# #48 — mike docs versioning (library-first)

Branch `feat/48-scaffold-mike-doc-versioning`. Backports the `scaffold-mike-doc-versioning`
lesson. **Scope decided 2026-07-19: library-first** — ship mike fully for `lib-minimal` now;
the service tiers (mvc/ddd) keep today's Actions-source docs deploy and get a **follow-up
issue**. (The lesson's "consumer pinned to an old release needs the docs for that release"
rationale is the *library* case; services are deployed, not published.)

**Do NOT delete this file when done** — tick the last box + "Completed — kept as a record".

## Architecture change (library only)

Today (all tiers): Pages source = **GitHub Actions**; `docs.yaml` deploys via
`configure-pages`/`deploy-pages`; `enable_pages.sh` sets `build_type=workflow`.

mike (lib-minimal only): Pages source = **gh-pages branch**; `docs.yaml` = **strict-build
check only**; the **release** workflow runs `mike deploy` → `gh-pages`; `enable_pages.sh`
flips Pages to the branch source **only once `gh-pages` exists**.

Constraint: `enable_pages.sh` lives in **python-common** (shared by every tier's `make init`),
so it must be **model-aware** (detect `provider: mike` in mkdocs.yml) — not rewritten
lib-only, which would break the services still on Actions-source.

## Tasks

- [x] `templates/lib-minimal/pyproject.toml` — added `mike = ">=2.1.0"` to the docs group
- [x] `templates/lib-minimal/mkdocs.yml` — `extra.version.provider: mike`
- [x] `templates/lib-minimal/.github/workflows/docs.yaml` — now strict build check only
      (push + **PR**); dropped `pages`/`id-token` perms, `configure-pages`,
      `upload-pages-artifact`, the `deploy` job and the `concurrency` group
- [x] `templates/lib-minimal/.github/workflows/release-pypi.yaml` — added `deploy_docs`:
      `needs: [pypi, details]`, `if: needs.details.outputs.suffix == ''` (prerelease guard),
      `permissions: contents: write`, `fetch-depth: 0`, `--with docs`, bot git identity,
      `X.Y` via `cut -d. -f1-2`, `mike deploy --update-aliases --push X.Y latest` +
      `mike set-default --push latest`. Version passed via `env:` (no `${{ }}` in `run:`)
- [x] `templates/python-common/bin/enable_pages.sh` — **model-aware** (`uses_mike` greps
      `provider: mike` in `mkdocs.yml`): mike → PUT/POST branch source `gh-pages`, guarded by
      `remote_branch_exists` so Pages is never pointed at an empty branch; else
      `build_type=workflow`. Still idempotent + non-blocking. **Note:** the old "already
      enabled → return" early-exit was removed on purpose — a repo enabled with the *wrong*
      source must be flippable (PUT vs POST is chosen by probing)
- [x] `templates/python-common/Makefile` + `tasks.sh` — help text + comments now describe the
      auto-detected model (kept in sync across both files)
- [x] lib-minimal `docs/contributing.md` — rewrote the Pages section for the mike flow
      (workflow split table, X.Y granularity, prerelease rule, first-release ordering)
- [x] lib-minimal `CLAUDE.md` — release section documents mike + the strict-build-only docs.yaml
- [x] **Services follow-up filed: #83** (Backlog) — Option A (leave services on Actions-source)
      recommended, Option B (extend mike) scoped
- [x] Fixed a `make lint` drift the harness caught: `shfmt` wants the pipe **at end of line**,
      not a leading `|` after a backslash continuation (the "shipped files must already pass the
      formatters" rule)
- [x] Verify: **lib-minimal 3 passed / mvc-native 128 passed**, both "scaffolds clean, lints
      clean, unit tests pass" after the shfmt fix. Also verified in a real scaffold that the
      model detection fires correctly on both sides: a scaffolded library reports `mike model`,
      a scaffolded service reports `Actions model` — the two Pages models coexist, and the
      shared script did not regress the service tiers.

**Completed 2026-07-19 — kept as a record.** Shipped library-first per the scope decision;
the service-tier decision lives on as #83.

## Notes
- Only document versions that actually published (deploy_docs runs after the `pypi` job).
- Default granularity **X.Y** (the template bumps minor per release); history forward-only.
- Origin lesson: `~/.claude/memory/lessons/scaffold-mike-doc-versioning-in-python-common.md`.
