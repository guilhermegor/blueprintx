# **Contributing**

Everything you need to develop, test, and ship changes to this service.

> **See also:** [Usage](usage.md) · [Architecture](architecture.md) · the repository's root
> `CONTRIBUTING.md` holds the authoritative branch/PR and commit-message policy.

---

## Setting up for development

The project ships both a `Makefile` and a parallel `tasks.sh` — use whichever suits your
machine (`make init`, or `bash tasks.sh init` when `make` is unavailable).

```bash
make init        # seed .env, create the Poetry venv + install deps, install pre-commit hooks
```

`init` composes `ensure_env` (seed `.env`), `venv` (create the Poetry virtualenv, install all
deps), and `precommit` (install the git hooks). Poetry is auto-installed if missing.

## Tests and linting

```bash
make unit_tests          # poetry run pytest tests/unit/
make integration_tests   # poetry run pytest tests/integration/
make lint                # ruff + mypy + codespell + pydocstyle + shell/sql/yaml gates
```

CI runs the same gates on every pull request; keep them green locally before pushing.

## Publishing the documentation (GitHub Pages)

Docs are **versioned via [mike](https://github.com/jimporter/mike)** and served from the
`gh-pages` branch. The `Docs - Strict Build Check` workflow only *builds* the site with
`--strict` on every push and PR (catching broken links before a release) — it never deploys.
Deployment is owned by the **Release** action: after it cuts the `vX.Y.Z` tag it runs
`mike deploy <X.Y> latest`, so the published site is versioned and only ever reflects versions
that actually shipped (a prerelease suffix is skipped and never moves `latest`).

GitHub Pages must be set to **"Deploy from a branch → gh-pages"**. That first-time enablement
**cannot** be done by the workflow itself (its `GITHUB_TOKEN` cannot create the Pages site from
scratch), so do the one-time enable with repo-admin rights:

```bash
make enable_pages          # or: bash tasks.sh enable_pages
```

This step already runs inside `make init` / `bash tasks.sh init`. It is **idempotent and
non-blocking**: it waits until the first release creates the `gh-pages` branch (mike creates it
on its first deploy), does nothing if Pages already points there, and just warns and continues
if `gh` is absent/unauthenticated, no remote resolves, or you are not a repo admin (a fork) — it
never breaks `init`. Manual alternative: *Settings → Pages → Build and deployment → Source:
Deploy from a branch → gh-pages*.

## Pull requests

1. Branch off the default branch following the prefix policy (`feat/…`, `fix/…`, …).
2. Fill out the PR template completely.
3. Ensure the CI checks (tests, lint, docs build) pass — they are the merge gate.

## Releasing

> **`main` is protected — you never commit or push to it directly.** All changes land via a
> branch → Pull Request → merge (online), or `make new_branch` → `make git_merge_to_main`
> (offline). Cutting a release means creating a `vX.Y.Z` git tag; the Changelog page is then
> generated from that tag by `cz changelog` on the docs build.

This service is deployed, not published to a package index.

**With a GitHub remote (online):**
1. Land your work on the default branch through a Pull Request (CI is the merge gate).
2. Run the **Release** action (Actions → Release → *Run workflow*), entering the version
   (e.g. `1.4.0`). It creates the `v1.4.0` tag and a GitHub Release server-side — no direct
   push to protected `main`.
3. The docs deploy regenerates the Changelog from the new tag automatically.

**Without a GitHub remote (offline):**
1. `make new_branch NAME=feat/my-change` — branch off the default branch.
2. Do the work and commit (Conventional Commits).
3. `make bump_version` — runs `cz bump`: computes the next version from your commits, updates
   `pyproject.toml`, regenerates `CHANGELOG.md`, and creates the `vX.Y.Z` tag.
4. `make git_merge_to_main` — merges the branch into the protected default branch locally.
5. Preview the Changelog any time with `make changelog`.

## Branding the docs site

The scaffold ships a **placeholder** brand image at `docs/assets/logo.png`, wired as the header
logo/favicon (`theme.logo` / `theme.favicon` in `mkdocs.yml`) and as the landing hero on
`docs/index.md`. To brand your site:

1. Replace `docs/assets/logo.png` with your own asset (keep the filename, or update the two
   `mkdocs.yml` paths and the `<img>` in `docs/index.md`).
2. Tune size and placement in `docs/stylesheets/extra.css` — the `.hero-logo` rule: `max-width`
   scales it, and the side margins (`margin: … auto` centers; `float` aligns left/right).

## Repository protection & security (one-time, scripted)

`make init` runs three admin-gated helpers. They are **idempotent and non-blocking**: without
`gh`, without auth, without a GitHub remote, or without repo-admin rights they warn and skip, so
`init` still completes for contributors and offline scaffolds. Re-run any of them alone later:

| Target | What it provisions |
|--------|--------------------|
| `make enable_pages` | GitHub Pages source (gh-pages branch for versioned docs, else Actions) |
| `make enable_repo_rules` | The `pr-quality-gate` branch ruleset + the merge settings the PR gate needs |
| `make enable_security` | Private vulnerability reporting, Dependabot alerts, Dependabot security updates |

### The `pr-quality-gate` ruleset

Applied to `~DEFAULT_BRANCH` (that ref survives a branch rename), looked up **by name** so a
re-run updates in place instead of creating a duplicate:

| Rule | Setting | Why |
|------|---------|-----|
| `pull_request` | `required_approving_review_count: 0` | ⚠️ **Must be 0.** GitHub forbids approving your own PR, so any value ≥ 1 locks a solo maintainer out of merging their own work. Zero still forces every change through a PR — that is the real guardrail. |
| `pull_request` | `required_review_thread_resolution: true` | Makes review comments **binding**: an unresolved thread blocks the merge instead of being decorative. |
| `code_scanning` | CodeQL, security `high_or_higher`, alerts `errors` | Alerts stay at `errors`: `errors_and_warnings`/`all` start blocking merges on stylistic queries, duplicating ruff/mypy with noise. |
| `copilot_code_review` | `review_on_push: true` | Its **own rule type** — not a `pull_request` parameter (that returns HTTP 422 and makes the feature look UI-only). |
| `non_fast_forward`, `deletion` | on | No force-push, no branch deletion on the default branch. |
| `required_status_checks` | **empty by default** | ⚠️ Deliberate. A required check whose name never reports blocks **every** PR forever. Populate `REQUIRED_CHECKS` in `bin/enable_repo_rules.sh` from a real PR — `gh api repos/:owner/:repo/commits/<sha>/check-runs --jq ".check_runs[].name"` — then re-run. |

**Deliberately not enabled:** *Require code quality results* (subjective AI severity on the merge
path — ruff, mypy and the `bin/check_*.py` gates already enforce quality deterministically) and
*Restrict code coverage* (preview; the floor is single-sourced in `.coveragerc` `fail_under`).

### Automatic vs manual — the boundary is repo config vs account plan

**Nothing here needs a click.** Every *repository* setting above is scripted. What is **not**
scriptable is your *account's* entitlement: the `copilot_code_review` rule only fires if the author
has access to Copilot code review, and **code review is not part of Copilot Free**. Without a
qualifying plan the rule sits correctly configured and **inert** — no review appears and nothing
errors. That silence is the trap, because the ruleset JSON looks perfect either way.

Every other rule (PR required, CI green, CodeQL clean) works regardless of any Copilot plan, so
the ruleset is worth applying unconditionally. Copilot Pro is free for verified students,
teachers and popular-OSS maintainers.

> Do **not** diagnose this with `gh api user/copilot_billing` → 404: that endpoint is for
> org/enterprise seat management and 404s for a personal account even when Copilot Free is active.

### Security

`SECURITY.md` at the repo root is auto-detected by GitHub (no API call) and flips *Security
policy* to Enabled; `make enable_security` turns on the matching private-reporting intake plus
Dependabot alerts and security updates. Ordinary version bumps are separate — see
`.github/dependabot.yml`, which uses `versioning-strategy: lockfile-only` so it refreshes
`poetry.lock` (keeping CI honest about what consumers install) without ever rewriting your
`pyproject` ranges.

## Automated PR flow (the quality gate)

Every PR is classified by `bin/pr_gate.py` (workflow `pr-gate.yaml`), which labels it, posts one
sticky comment with a per-axis status table, and hands the **safe classes** to GitHub's native
auto-merge. Two rules are the whole design:

**Classified by PATH, never by diff size.** The dangerous change is *semantic*, not big: a
one-character edit to a schema/contract constant is the smallest possible diff and the most
dangerous — and every test still passes, because the tests assert the contract that was written.
So size never decides eligibility; the changed paths do. (The one place size still matters — an
`XL` diff is vetoed — is **waived for a lockfile-only diff**, whose line count tracks how many
dependency hashes moved, not risk.)

| Risk class | Paths | Auto-merge? |
|------------|-------|-------------|
| `src` | `src/` | ❌ defines what "passing" means |
| `tests` | `tests/` | ❌ defines what "passing" means |
| `other` | anything unmatched | ❌ unknown = unsafe (default-deny) |
| `ci` | `.github/`, `bin/`, `Makefile`, `tasks.sh`, `.pre-commit-config.yaml` | ✅ |
| `deps` | `pyproject.toml`, `poetry.lock`, `requirements.txt` | ✅ (the test suite is the gate) |
| `docs` | `docs/`, `mkdocs.yml`, `README.md`, `CHANGELOG.md`, … | ✅ |

**Consent is opt-OUT.** The safe classes auto-merge with **no label**; add `do-not-merge` to force
a human merge. Native auto-merge **bypasses nothing** — GitHub holds the merge until every required
check of the ruleset is green, so the gate only decides *eligibility*, never *whether it passed*.

Edit the risk table (the `RISK_PATHS` constant) in `bin/pr_gate.py` for your project's real layout.

### ⚠️ After changing gate policy, backfill the open PRs

The gate runs on `pull_request` events, so a PR that was **already open** when you change the
policy (the classification/consent rules in `pr_gate.py`, or `allow_auto_merge` /
`delete_branch_on_merge`) is **never re-evaluated** — it keeps the labels and auto-merge state it
got under the old rules until some new event touches it. That is not a bug; the gate simply never
ran again. So after merging a policy change, run the backfill:

```bash
gh workflow run pr-gate.yaml -f backfill=true   # re-evaluates every open PR
# for a Dependabot PR, `gh pr comment <n> --body "@dependabot rebase"` also works
```

### Bot-merged PRs and the reconciler

A PR merged by **native auto-merge** (a bot action) does **not** close its linked issue and does
**not** delete its branch, even with `delete_branch_on_merge` on — bot-performed actions are
deliberately inert to prevent automation recursion. `pr-reconcile.yaml` fixes both: it closes the
`Closes #N` issues and deletes the head branch of merged PRs. Its **scheduled daily run is the
actual fix** — scheduled events are exempt from the "no new workflow runs" suppression that also
swallows the fast `pull_request: [closed]` path for a bot merge. Latency is up to one day; that is
the accepted cost of not needing a personal access token.

### The work-ledger gate

`bin/check_backlog_ledger.py` (pre-commit + CI) fails a branch that touches `src/` or CI paths but
adds no `docs/backlog/<kebab>_YYYYMMDD_HHMMSS.md` ledger with a `- [ ]` checklist — making the
per-branch work-ledger convention structural instead of a thing you remember. Routine
docs/deps/tests-only branches need none.
