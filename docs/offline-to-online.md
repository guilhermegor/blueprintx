# Promoting an offline scaffold to online

blueprintx#382. `bin/promote_offline_to_online.sh` turns an offline-scaffolded project into an
online one — a GitHub remote, the GitHub-only CI assets, branch protection — without
re-scaffolding and without hand-copying files out of BlueprintX.

Not registered in `mkdocs.yml` nav, matching the existing docs/issue-scope.md — operational/gate
documentation at the docs root, not a published skeleton page (see docs/CLAUDE.md's Type A/B/C
categories, none of which fit this).

## Why offline mode needs an inverse

`apply_offline_mode` (in every `bin/scaffold/python_*.sh` and `ts_react_app.sh`) runs once, at
scaffold time, when the developer declines a GitHub remote: GitHub-only assets are skipped, and
the offline git-diff workflow is copied in instead. Until this script, the only route back to
the online workflow was scaffolding a second project and moving the code across by hand.

## Why this is a standalone script, not a scaffold change

The 5 Python `bin/scaffold/python_*.sh` scripts and `ts_react_app.sh` are held by other PRs at
the time this shipped, so this script does not source or edit any of them — it transcribes their
`copy_github_assets` / `apply_offline_mode` manifests instead (see the table below) and runs
independently. It does not use `bin/enable_repo_rules.sh` or `bin/enable_security.sh` either —
neither exists in this repo (measured: `grep -rln "enable_repo_rules\|enable_security" bin/`
finds nothing); branch protection is applied inline via `gh api`.

## Usage

```bash
bin/promote_offline_to_online.sh <project_path> --tier <tier> [options]
```

| Flag | Required | Meaning |
|---|---|---|
| `<project_path>` | yes | Path to the offline-scaffolded project. |
| `--tier` | yes | One of the 6 tiers below. No inference — a wrong guess silently promotes the wrong inventory, so the caller must say which one. |
| `--github-user` | no | GitHub owner for the new repo. Default: `gh api user`. |
| `--visibility public\|private` | no | Default `private`. |
| `--deploy-target none\|pages\|vercel` | no | `react-spa-webpack` only. Default `none` (see caveat below). |
| `--publish none\|pypi\|test-pypi\|both` | no | `lib-minimal` only. Default `none` (see caveat below). |
| `--skip-branch-protection` | no | Skip the best-effort `gh api` branch-protection call. |

## What gets added, per tier

The 4 service tiers (`ddd-service-native-db`, `ddd-service-orm-db`, `mvc-service-native-db`,
`mvc-service-orm-db`) share one manifest — transcribed from `copy_github_assets()`, identical
across all four:

- `.github/workflows/{tests,secret_scan,review_threads,coderabbit_trigger,review_retry,pr-gate,pr-reconcile,contract_drift,release,docs}.yaml`
- `.github/CODEOWNERS` (envsubst `GITHUB_USERNAME`), `.github/CLAUDE.md`, `.github/PULL_REQUEST_TEMPLATE.md`, `.github/dependabot.yml`
- `SECURITY.md` (envsubst `PROJECT_DISPLAY_NAME`, `REPOSITORY`)

`lib-minimal` (from `lib_minimal_copy_github_assets()`) is the same shape minus
`contract_drift`/`release`, plus `docs.yaml` from its own `templates/lib-minimal/.github/workflows/`,
plus `release-pypi.yaml` / `release-test-pypi.yaml` gated by `--publish`.

`react-spa-webpack` (from `ts_react_app.sh`) ships only `.github/CLAUDE.md`, `.github/CODEOWNERS`
(plain copy, no envsubst), `.github/PULL_REQUEST_TEMPLATE.md`, and — gated by `--deploy-target` —
either `deploy-spa.yml` or `deploy-vercel.yml` + `vercel.json`. No `SECURITY.md` or
`dependabot.yml`: `templates/ts-common/` ships neither.

## The two "which one was it" gaps

Neither the original deploy target (react tier) nor the original publish target (lib-minimal)
survives into an offline project — `apply_offline_mode` removes `.github/` entirely for react,
and the workflow was simply never written for lib-minimal's unchosen options. This is the same
gap the issue names for tier itself ("no doctor artifact... no tier marker persisted"): nothing
records the choice, so the script defaults to `none` rather than guess, and documents the flag
instead. Pass `--deploy-target` / `--publish` explicitly if the original choice is known.

## What gets removed (or left, with a warning)

Python tiers: `bin/{git_diff_export,git_diff_apply,git_diff_check,new_branch,git_merge_to_main,protect_branch}.sh`,
`poe_tasks.offline.toml` (and its entry in `poe_tasks.toml`'s `[tool.poe] include` list), and the
swapped `.pre-commit-config.yaml` hook — `protect-branch` (local) is replaced back with the stock
`no-commit-to-branch`. React tier: the git-diff trio and the `git:diff:*` `package.json` scripts;
react's `apply_offline_mode` never swapped a pre-commit hook or wired poe, so neither is touched.

`git_diffs/` is removed only when it holds nothing but the `.keep` placeholder `apply_offline_mode`
created — real exported diffs a user actually placed there are left in place with a warning, never
silently deleted. `bin/lib/common.sh` is left alone in every tier: it is not in the offline-only
list `apply_offline_mode` ships, and other tooling may still use it.

## Preconditions — refuse loudly, never half-promote

Checked before any file is touched, in this order: the target is a git repository; not already
fully online (an `origin` remote **and** a populated `.github/workflows/` — that combination is a
clean no-op, exit 0); not in the ambiguous state of an `origin` remote **without** GitHub assets
(refuses — could be mid-promotion or a manually-added remote, and guessing which is exactly what
this script exists not to do); the working tree is clean; `gh` is installed and authenticated;
the `--tier` is one of the 6 known tiers **and** `templates/<tier>/skeleton.meta` still exists in
this BlueprintX checkout (an unknown or since-removed tier fails loudly rather than copying
nothing and reporting success).

## Idempotency

Every mutation is independently safe to re-run: file copies overwrite identical content, removals
use `-f`/check-first, the poe-include and pre-commit-hook edits detect their own prior
application and no-op, and `package.json` script stripping is a `dict.pop(..., None)`. A run
interrupted partway (`set -euo pipefail` stops at the first failure) resumes cleanly on the next
invocation — nothing needs to be undone by hand first.

## Verification

`bash -n` and `shellcheck --severity=warning --exclude=SC1091` pass clean (mirrors CI's
`shellcheck` pre-commit hook). `tests/test_promote_offline_to_online.sh` exercises the refusal
paths (not a git repo, unknown tier, dirty tree, `gh` missing/unauthenticated, an `origin` set
without GitHub assets) and the already-online no-op, against throwaway local git repos with no
network or `gh` auth required.

**Not verified here, and stated rather than glossed over:** a live round trip (scaffold offline →
promote → diff against an online scaffold of the same tier) needs a real `gh`-authenticated
environment with network access to create a repository — the should-fail witness the issue asks
for ("diff the two trees and report the count"). That is a manual verification step for whoever
runs this against a real project, not something this sandbox can execute.

## Relationship to #109 and #129

blueprintx#109 (doctor / template-drift check, open) shares this script's shape — reconcile a
scaffolded tree against BlueprintX's current idea of it — but compares against the *template*
where this compares against the *online inventory*. If #109 lands, promotion could become a mode
of it rather than a second walker; until then, keeping this standalone avoids inventing a tier
marker or a data-file abstraction (`.review-bots.yaml`-shaped) for a single consumer. Branch
protection here is inline `gh api`, independent of blueprintx#129's `bin/enable_repo_rules.sh`
(not yet merged at the time this shipped) — once that lands, this script's `apply_branch_protection`
is a natural place to delegate to it instead.
