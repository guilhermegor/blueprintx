# Secret scanning in scaffolded projects

Two scanners, with different defaults:

| Scanner | Needs an API key | Default | Where |
|---|---|---|---|
| **gitleaks** | no | **on** | every tier |
| **GitGuardian** (`ggshield`) | yes | opt-in | Python tiers |

`gitleaks` is the default because it is the only one that can be. A freshly
scaffolded project has no GitGuardian account and no key, and `ggshield`
with no key exits 3 having scanned nothing — so an unconditional GitGuardian
job is a project red on its first PR, not a project that is protected.

## What GitGuardian adds over gitleaks — measured

Measured on this tree (2026-09-20), not quoted from a vendor page:

| | gitleaks 8.30.1 | ggshield 1.54.0 |
|---|---|---|
| Scan of the BlueprintX tree (4.76 MB) | 0 findings, exit 0, 1.52 s | **could not run** — exit 3, no key |
| Planted synthetic credentials (GitHub PAT, Slack bot token, AWS secret shapes) | **3 findings, exit 1** | could not run |
| API key required | none | yes, and BlueprintX's own key fails auth (`Invalid GitGuardian API key`) |

**GitGuardian's measurable delta over the installed gitleaks is currently
zero**, because it cannot be made to run here at all. Its documented
advantages — a hosted dashboard, incident history, a larger proprietary
detector set, and validity checking that confirms a found credential is
*live* — are real product features, but none of them are observable from
this repository without a working paid key. So gitleaks carries the default
and GitGuardian stays an opt-in for anyone who has an account.

One finding from that measurement is worth keeping: the first should-fail
probe used AWS's own documented example access key — the `AKIA…EXAMPLE`
value printed throughout the AWS docs — and gitleaks reported **no leaks**.
It allowlists that value by design, precisely because it appears in so much
documentation. A should-fail test built on a documented example key proves
nothing; the fixture has to be a shape a real detector fires on, generated
at test time rather than checked in.

## Which tiers scan, and with what

- **Python tiers** — `gitleaks` via `bin/check_secrets.sh`, wired as both a
  pre-commit hook and a CI job, plus the opt-in GitGuardian workflow below.
- **TypeScript tiers** (`react-spa-webpack`, `ts-lib`) —
  `.github/workflows/secret-scan.yml`, `gitleaks` on every push and PR.
- **bash-cli** — the `secret-scan` job in `.github/workflows/ci.yml`, same
  scanner.

All three use the same pinned, checksum-verified gitleaks install and
`fetch-depth: 0`, so history is scanned and not just the tip. The
non-Python tiers deliberately ship **no** `.gitleaks.toml`: gitleaks falls
back to its embedded default ruleset, and an allowlist is added only for a
measured false positive, never preemptively.

## Why GitGuardian is opt-in

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
gh secret set GITGUARDIAN_API_KEY --repo <owner>/<repo>
```

`gh` prompts for the value when neither `--body` nor stdin supplies one. Prefer that
prompt over `--body '<your key>'`: an argument is visible to any other process on the
host for the life of the call, and it lands in your shell history besides.

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
