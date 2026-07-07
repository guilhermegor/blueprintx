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
- [ ] real online scaffold smoke against a throwaway GitHub repo: `git status --porcelain`
      empty + `gh repo view --json description` set. **Manual-only**: the scaffolder is
      interactive (no non-interactive path) and the online branch creates a real GitHub repo +
      branch protection — run by hand with go-ahead; not safe to automate.
- [x] open PR (#44)

Delete this file once every box is `[x]`.
