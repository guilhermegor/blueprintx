# gitleaks secret scanning (blueprintx#305, gitleaks slice)

`Refs #305` — that issue proposes six tools (gitleaks, osv-scanner, jscpd, semgrep,
`EXCEPTIONS.md`, baseline histograms) and stays open for the other five. This PR is the
**gitleaks slice only**, per the issue's own instruction that each tool needs its own PR.

## Why

BlueprintX chose GitGuardian (#155, PR #286). Its `GITGUARDIAN_API_KEY` measurably fails auth
(`Invalid GitGuardian API key`, exit 3), and the owner already rejected propagating that key
into every scaffolded project — correctly, since BlueprintX is public. gitleaks needs no API
key and no account, so it becomes the shipped default for generated projects; GitGuardian
stays available for anyone who wants the hosted product. Additive, not a replacement — PR
#286's files are untouched.

## Scope

- [x] `.gitleaks.toml` at the repo root — `[extend] useDefault = true` + a narrow,
      `regexTarget = "match"`-scoped allowlist entry for the one measured false positive
      (`generic-api-key` on `sweagent-capi:claude-opus-4.6`, a Copilot model identifier in
      `docs/backlog/pr-gate-blocks-merge_20260817_104500.md:186`).
- [x] `.gitleaks.toml` in `templates/python-common/` — ships to every generated Python
      project's root; minimal allowlist (its own config + `poetry.lock`) plus a stopwords
      list for placeholder markers, no speculative entries copied from ditto's own app
      surface.
- [x] `templates/ts-common/` — investigated, **not added this PR**. It has no `bin/`
      directory and its pre-commit path is husky + lint-staged, a different mechanism from
      the `bin/check_*.sh` pattern this PR follows. Wiring gitleaks there (husky hook + CI
      job + config copy) is materially more scope than the runner-script pattern used here;
      left for a follow-up if wanted. BlueprintX's own repo-root `.gitleaks.toml` already
      covers `templates/ts-common/`'s own source as part of this repo's history.
- [x] One implementation: `templates/python-common/bin/check_secrets.sh`, bulk-copied via
      `cp -r templates/python-common/bin/.` (no copy-list entry). Invoked from both sides:
      BlueprintX's own root pre-commit hook + new `secret_scan.yml` workflow (via `--root .`,
      same pattern as `check_complexity.sh`), and every generated project's own pre-commit
      hook, `poe lint` / `poe check_secrets`, and CI (`tests.yaml`).
- [x] Resolve-don't-install: graceful skip when gitleaks is absent locally,
      `GITLEAKS_REQUIRED=1` hard-fails in CI (mirrors `LINT_ACTIONS_REQUIRED`).
- [x] Should-fail witness: planted gitleaks' own documented AWS test key in a throwaway
      `/tmp` sandbox (never the tracked tree) — confirmed non-zero exit + finding.

## Verification

- `LINT_ACTIONS_REQUIRED=1 bash bin/ci/check_actions.sh` — clean (27 workflows, all bounded).
- `bash bin/ci/check_shell.sh` — clean.
- `bash bin/ci/scaffold_lint_test.sh lib-minimal` — scaffolds a real project and runs its own
  `poe lint` / `poe unit_tests` / `poe integration_tests`, proving `check_secrets.sh` runs
  inside a generated project.
- `gitleaks git . --no-banner --redact -v` at repo root — 0 leaks with the new config.

Completed — kept as a record.
