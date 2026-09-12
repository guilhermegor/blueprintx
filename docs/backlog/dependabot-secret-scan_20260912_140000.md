# Dependabot secret scan (blueprintx#457)

## Problem

Every Dependabot PR fails the `GitGuardian — secret scan` job (defined in
`.github/workflows/scaffold_checks.yml`'s `secret-scan` job — **not** in
`.github/workflows/secret_scan.yml`, which is the separate gitleaks job) forever, because the
job never actually runs: `ggshield` exits 3 with `Invalid GitGuardian API key`.

## Root cause (measured, not assumed)

- `GITGUARDIAN_API_KEY` **is** set as a repo (Actions) secret on `blueprintx` since
  2026-08-27, and resolves fine on a human-authored PR — measured: PR #455's
  `GitGuardian — secret scan` check is `SUCCESS`.
- GitHub gives a **Dependabot-triggered** run a separate secret store. Repo Actions secrets
  are not exposed to it; only secrets registered under *Dependabot secrets* are, and this repo
  has zero (`gh api repos/guilhermegor/blueprintx/dependabot/secrets --jq .total_count` == 0).
- Measured on PR #400, job 103472359681: the step's own env dump shows
  `GITGUARDIAN_API_KEY: ` (blank), followed by `Error: Invalid GitGuardian API key.`, exit 3.
  So the key is not a bad value — it resolves to an **empty string** specifically on the
  Dependabot-triggered run.
- Not a fork-PR restriction (`GITHUB_TOKEN` secrets-to-forks limitation): Dependabot PRs are
  same-repo, not a fork, and the mechanism is the separate Dependabot secret store, confirmed
  by the `dependabot/secrets` API call above returning 0.

## Relationship to #155 / #287

- #155 is the parent "ship GitGuardian everywhere" epic; this repo's own CI + pre-commit slice
  of it is done (the key exists, human PRs pass). #457 is a gap #155 did not anticipate:
  Dependabot's separate secret store.
- #287 is about **scaffolded-project** GitGuardian wiring (the key never reaches a newly
  created repo at all). #457 is about **this repo's own** CI, where the key already exists —
  a narrower, different failure mode of the same underlying tool. #287's option 1 ("skip but
  report loudly") is the shape this fix reuses, scoped specifically to the bot-author signal
  rather than "no key at all".

## Fix

Both `.github/workflows/scaffold_checks.yml`'s `secret-scan` job (this repo) and
`templates/python-common/.github/workflows/secret_scan.yaml` (every scaffolded project) gain a
step that reports and skips the `ggshield` run **only** when the PR author (from
`github.event.pull_request.user.login`, never `github.actor`) ends in `[bot]` — reusing
`bin/check_backlog_ledger.py`'s `is_bot_author` precedent rather than inventing a second
mechanism. Not a silent pass: it prints a `::warning::` naming the reason and the one-line
remedy, and root-repo `gitleaks` already covers the same range unconditionally, so no scan
coverage is actually lost on this repo. A human PR with a genuinely missing/bad key still
fails loud, unchanged.

## Manual follow-up (needs a human — the actual key value is not available to this agent)

```
gh secret set GITGUARDIAN_API_KEY --app dependabot --repo guilhermegor/blueprintx
```

## Checklist

- [x] Reproduce and confirm root cause (Dependabot secret store, not fork restriction)
- [x] Patch `.github/workflows/scaffold_checks.yml`'s `secret-scan` job
- [x] Patch `templates/python-common/.github/workflows/secret_scan.yaml`
- [x] `bash bin/ci/check_actions.sh` passes
- [ ] Human runs `gh secret set GITGUARDIAN_API_KEY --app dependabot --repo <owner>/<repo>`
      to close the gap for real (this agent cannot read the existing key's plaintext value)
- [x] PR opened, `Closes #457`
