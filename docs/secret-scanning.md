# Secret scanning (GitGuardian) in scaffolded projects

Every Python skeleton ships a GitGuardian (`ggshield`) secret-scan workflow
(`.github/workflows/secret_scan.yaml`) — but only when you ask for it. This
page explains the opt-in, why it exists, and what to do if you scaffolded
without it and want it later.

## Why opt-in

`secret_scan.yaml` reads `${{ secrets.GITGUARDIAN_API_KEY }}`, and GitHub
resolves that secret **in the repository where the workflow runs**. A key
set on `guilhermegor/blueprintx` never reaches a freshly scaffolded project
— so shipping the workflow unconditionally meant a brand-new project failed
its very first PR (`ggshield` exits 3, "A GitGuardian API key is needed to
use ggshield") for a scanner nobody asked to enable. blueprintx#287 tracked
this; the fix is to ship the workflow only when the key is actually
available to propagate.

## How to opt in

Export `GITGUARDIAN_API_KEY` in your shell **before** running `make new` /
`bin/blueprintx.sh`:

```bash
read -rs GITGUARDIAN_API_KEY   # paste your GitGuardian personal or team API key
export GITGUARDIAN_API_KEY
make new
```

When you answer **yes** to "Add remote origin and (optionally) create the
GitHub repo now?", the scaffold:

1. copies `.github/workflows/secret_scan.yaml` into the new project (only
   because the variable is set — see `copy_github_assets` in each
   `bin/scaffold/python_*.sh`), and
2. propagates the key to the new repository's secrets for you
   (`scaffold_set_secret_scan_key` in `bin/lib/scaffold_git_remote.sh`),
   the same moment `GH_PAT_REVIEW_TRIGGER` is propagated for
   `coderabbit_trigger.yaml`.

Decline, or never export the variable, and the project simply never
receives the workflow — no dead job, nothing failing on the first PR.

## Never commit the key

`GITGUARDIAN_API_KEY` is read from your shell environment only. No
BlueprintX file — template, `.env.example`, or otherwise — ever holds the
literal value; only the secret **reference** (`${{ secrets.GITGUARDIAN_API_KEY }}`)
is checked in. This repo does not document GitHub Actions secrets in any
tier's `.env.example` (that file is seeded into the generated project's own
`.env` and covers **application runtime** configuration — database
credentials, feature flags — never CI-time secrets); the precedent for a
repo secret like this one is a comment in the workflow file that needs it,
which is what `secret_scan.yaml`'s own header — and this page — follow.

## Opting in after the fact

Scaffolded without the key and want GitGuardian anyway?

```bash
gh secret set GITGUARDIAN_API_KEY --repo <owner>/<repo> --body '<your key>'
```

then copy `templates/python-common/.github/workflows/secret_scan.yaml` from
a BlueprintX checkout into the project's own `.github/workflows/`.

## The fail-loud contract, once shipped

A missing or bad key still fails **loudly**, never silently:

- No key at all → `ggshield` itself exits 3 ("A GitGuardian API key is
  needed to use ggshield"), distinct from a clean scan's exit 0.
- A Dependabot-authored PR is the one deliberate, reported exception
  (blueprintx#457): GitHub gives it a separate secret store this repo's key
  never reaches, so the job prints a `::warning::` naming the reason and
  skips — `gitleaks` (`tests.yaml`) already scans the same range
  unconditionally, so nothing goes unscanned.

## Offline scaffolds never receive it

A scaffold run that declines a GitHub remote (`apply_offline_mode`) strips
every GitHub-only workflow, `secret_scan.yaml` included — there is no
Actions runner to execute it there. `bin/ci/scaffold_lint_test.sh` asserts
this for every tier.
