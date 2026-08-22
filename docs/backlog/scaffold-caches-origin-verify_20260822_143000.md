# Scaffold hygiene — shipped caches (#205) and an unverified `origin` (#212)

Created 2026-08-22. Two defects on the same seam: things the scaffold does to the
*generated* project that nothing downstream ever reports. Bundled because they share a
branch, a review and a verification run — not because they share a cause.

## #205 — `cp -r` ships `templates/**/__pycache__` into generated projects

- [x] Add `scaffold_purge_caches` to `bin/lib/common.sh` — ONE implementation, called from
      each tier's `main` right before `initialize_git_repo`, rather than an exclusion
      argument repeated at ~30 `cp -r` call sites (and no new rsync dependency)
- [x] Cover `__pycache__`, `.pytest_cache`, `.ruff_cache`, `.mypy_cache` and loose `*.py[cod]`
- [x] Wire the call into all six scaffolds (4 service tiers, lib-minimal, react-spa)
- [x] Negative control in `bin/ci/scaffold_lint_test.sh`: **seed** cache dirs into
      `templates/` before scaffolding, then `find` the generated tree and fail on any hit.
      Seeding is the whole point — a fresh CI checkout has no caches, which is precisely
      why this shipped unseen. The seed is removed in the `EXIT` trap.
- [x] Guard the seeding: only seed under a directory the template already has, and fail
      loudly if zero dirs were seeded, so the check can never pass vacuously
- [x] Verified by hand on `mvc-service-native-db`: with the purge, zero caches in the
      generated tree; with the purge disabled, **9** `__pycache__` dirs leak (more than
      were seeded — `templates/python-common/bin` and `tests/unit` carried their own)

## #212 — an existing `origin` was skipped without verifying where it points

- [x] `scaffold_add_git_remote` now reads the existing URL and compares it against the
      slug the scaffold was told to build; on mismatch it prints **both** URLs and returns
      non-zero, never guessing which the user meant
- [x] `scaffold_remote_slug` reduces ssh / scp-style / https / `ssh://` spellings of the
      same repo to one `owner/repo`, so a correctly-configured remote is not rejected; a
      non-GitHub URL reduces to itself and therefore never matches
- [x] `scaffold_prompt_git_remote_setup` returns 0 **only** for a present-and-verified
      origin, so callers can gate on the remote rather than on "the prompt returned"
- [x] `python_lib_minimal.sh` — `apply_branch_protection` moved behind that gate
- [x] `ts_react_app.sh` — `apply_branch_protection` **and** `prompt_pages_setup` moved
      behind it (the AC named this one explicitly)
- [x] The four service tiers keep `|| true`: `main` already routes "no verified remote" to
      offline mode via its `@{u}` check, and `set -e` must not abort the scaffold
- [x] Negative control `bin/ci/check_git_remote_guard.sh` — six `scaffold_add_git_remote`
      cases (3 pass, 3 fail) plus five slug-reduction cases; wired to pre-commit
      (`git-remote-guard`) and to a new `git-remote-guard` CI job
- [x] Control on the control: neutering the comparison to `if true` makes the check fail
      with exactly the three mismatch assertions. It has teeth.

## Review round 1 (CodeRabbit on #215) — four findings, all valid

- [x] **Host confusion, Major.** `scaffold_remote_slug` matched `github.com` as a SUBSTRING and
      cut at the last occurrence, so `https://evil.example/github.com/octocat/widget.git`
      reduced to `octocat/widget` and the guard accepted an arbitrary host — defeating #212 for
      exactly the crafted input it exists to stop. Reproduced before fixing. Now parses the
      supported URL forms and anchors the host; `github.com.evil.com/...` misses too.
- [x] **Push URL never checked, Major.** `git remote get-url origin` returns only the FETCH
      url, so a remote that fetches from the right repository could push elsewhere — and the
      push is the whole risk. Now checks `--all` fetch **and** `--push --all`.
- [x] **`|| true` was not the fix it looked like, Major.** Each `main` selects online mode with
      `rev-parse @{u}`, which answers "is there an upstream?", never "is it OURS" — true for a
      pre-existing clone. A refusal was swallowed and the online path still pushed. All six
      selectors now also require `SCAFFOLD_REMOTE_VERIFIED=1`, set by the lib.
- [x] **Status-only assertion, Minor.** `expect_add_remote` checked the exit code only; a pass
      that added no remote, or a fail that rewrote the existing one, both slipped through. It
      now asserts the resulting origin state in both directions.
- [x] **Seeding covered one of four cache types, Minor.** The assertion rejects `__pycache__`,
      `.pytest_cache`, `.ruff_cache`, `.mypy_cache` and loose `*.py[cod]`; only the first was
      ever seeded, so three quarters of it could not fail — the same vacuous shape the seeding
      exists to close, inside the PR that added the seeding. All five now seeded.
- [x] 3 new host-confusion slug cases, 2 new refusal cases, 1 push-URL case; the tier harness
      re-run green on `mvc-service-native-db`.

## Not done here, deliberately

- The six copies of `initialize_git_repo` are still six copies. Deduping them is the
  #189-shaped refactor, and folding it into a two-defect fix would bury both.
- `bin/blueprintx.sh` was left alone: CI invokes the scaffold scripts **directly**
  (`scaffold_lint_test.sh` reads `scaffold=` from the meta), so a purge placed in the
  dispatcher would be a gate CI can never exercise — the same blindness #205 is about.

## Completed — kept as a record

Both issues closed by the PR on `fix/scaffold-caches-origin-205-212`.
