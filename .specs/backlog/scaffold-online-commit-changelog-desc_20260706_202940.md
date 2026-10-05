# Scaffold online-commit fix + blueprintx changelog wiring + gh repo description

Branch: `fix/scaffold-online-uncommitted-changelog-desc`

## Part A — fix uncommitted online files (root cause)
- [x] Service tiers: reorder `strip_bump_version` before `commit_and_push_github_assets`
      (`python_mvc_service.sh`, `python_mvc_service_orm.sh`, `python_ddd_service.sh`,
      `python_ddd_service_orm.sh`)
- [x] lib-minimal: add `commit_online_artifacts` + call it last in the online branch
- [x] shellcheck + `bash -n` all 6 edited scaffolds

## Part B — wire blueprintx root CHANGELOG.md into docs
- [x] `pyproject.toml`: add `[tool.commitizen]`
- [x] `mkdocs.yml`: add `pymdownx.snippets` (base_path `.`)
- [x] `docs/changelog.md`: rewrite to `--8<-- "CHANGELOG.md"` + GitHub Releases link
- [x] generate root `CHANGELOG.md` (`cz changelog`)
- [x] `Makefile` + `tasks.sh` + `bin/help.sh`: `changelog` target (parity)
- [x] `.github/workflows/docs.yml`: fetch-depth 0 + install commitizen + `cz changelog` before build
- [x] `docs/CLAUDE.md`: update changelog.md index row
- [x] strict `mkdocs build` passes; snippet renders entries

## Part C — gh repo description from CLI answer (online)
- [x] add `--description "$PROJECT_DESCRIPTION"` to `gh repo create` in all 6 scaffolds

## Housekeeping
- [x] global lesson `scaffold-mutations-before-final-commit.md` + README index
- [x] mirror in `docs/blueprintx-lessons.md`

## Verify (final)
- [x] CI checks green: check_spelling / check_shell / check_version_sync / validate_meta
- [x] strict `mkdocs build` passes; changelog snippet renders
- [x] Part A mechanism proven: sourced real `commit_online_artifacts` against a local bare
      remote → 3 dirty files → clean tree, 0 ahead/0 behind, sweep commit present
- [x] `act` on changed `docs.yml` — superseded by the real "Docs - Github Page Deployment"
      run on `main` (merge commit `00ef87e`, PR #44): completed / success. The live runner
      is a stronger signal than `act`, so this is closed.
- [x] real online scaffold smoke against a throwaway GitHub repo: ran the lib-minimal online
      scaffold (driving the real `python_lib_minimal.sh` prompts) into a private `bx-smoke-*`
      repo → `git status --porcelain` empty, `main...origin/main` 0 ahead/0 behind (Part A),
      and `gh repo view --json description` = "BlueprintX online smoke test" (Part C). Repo
      deleted after (needed the `delete_repo` token scope).
- [x] open PR (#44)

Completed — kept as a record. Do NOT delete completed backlog files: they document what
was done and why for the team. (Global rule; only delete when a specific repo opts in.)
