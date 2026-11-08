# Contributing

## Branch naming

`<N>` is the issue number; the `branch-has-issue` workflow rejects a branch without it
(`release/`, `dependabot/` and `renovate/` are exempt).

| Type | Pattern |
|------|---------|
| Feature | `feat/<N>-<short-description>` |
| Bug fix | `fix/<N>-<short-description>` |
| Docs | `docs/<N>-<short-description>` |
| Refactor | `refactor/<N>-<short-description>` |
| Chore | `chore/<N>-<short-description>` |

## Commit style

Use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(scope): add user authentication
fix(api): handle null response from /users
docs: update README setup steps
```

## Code style

- Prettier formats on save (`.prettierrc.js`)
- ESLint enforces rules on save (`eslint.config.js`)
- TypeScript strict mode is enabled — no `any` without justification
- Functions are capped at 60 lines via `max-lines-per-function` — 100 for
  *every* function in a `.tsx`/`.jsx` file, not only a component body, since
  the rule is scoped by file glob (`src/**/*.{tsx,jsx}`) and a helper defined
  alongside a component gets the same ceiling
- Errors must narrow before use: this covers a `catch (err)` clause **and** a
  promise `.catch(cb)` parameter, which `strict` mode alone leaves as `any` —
  see `CLAUDE.md`'s "Function length" / "Catch safety" sections for the reasoning

## Test order and seed-specific failures

Jest runs tests in a **randomised order** (`randomize: true` in `jest.config.cjs`) so a test
that only passes because an earlier one ran first fails instead of passing silently. Every
run reports the seed it used; reproduce that order by passing the number back yourself as
`jest --seed=<N>`. Jest reports the seed, not a ready-made re-run command.

**A test that fails only under a particular seed is a real defect, never flakiness to
re-run away.** Re-running until it goes green hides the exact bug this exists to catch —
report the seed and the failing test instead of retrying.

## Assertion weakening

`==` is not implied by `>`, `<`, `>=` or `<=`: turning `expect(x).toBe(5)` into
`expect(x).toBeGreaterThan(5)` accepts infinitely many values the old assertion rejected, so a
red test goes green without the behaviour being fixed. `src/**/assertion-weakening.cjs` compares
every changed `*.test.*` / `*.spec.*` file against the merge-base and fails when a `toBe`,
`toEqual` or `toStrictEqual` in a test became `toBeGreaterThan`, `toBeLessThan`,
`toBeGreaterThanOrEqual` or `toBeLessThanOrEqual`. It checks `*.{test,spec}.{ts,tsx,js,jsx}` files only (not `.mts`/`.cjs` variants or `__tests__/` files). It judges a change from
equality, so assertions that were always inequalities (thresholds, budgets) are untouched, and
strengthening an inequality to equality passes. It runs in `.husky/pre-commit` and in the lint
workflow, which checks out full history.

When the expectation was provably wrong, justify the change: put `test-change-ok: <reason>` in the
PR body (CI reads it from the event payload, so a re-run after editing the body keeps the old
text; push a new commit) or in the trailer of an earlier commit on the branch. The commit that
introduces the weakening cannot carry its own trailer, because the hook runs before the message
exists: prefix that commit with `TEST_CHANGE_OK='<reason>'` AND put the same `test-change-ok:`
trailer in its message. The gate re-checks the whole branch since the merge-base on every later
commit, and the env var is not stored, so only the trailer carries the justification forward.
Matching is by matcher multiset within a test (same-named tests only): a test that loses a
`toBe` and gains an unrelated `toBeGreaterThan` is reported, and a loosening masked by another
`toBe` added in the same test is not. The justification covers the first case. A failing `git`
call makes the gate fail rather than pass.

## Pull requests

1. Open an issue first, using the repository's issue template. State what you want to change
   and why, and list the files it will touch. For non-trivial work, wait for the issue to be
   accepted before writing code.
2. Branch off the default branch as `<type>/<issue-number>-<slug>` (for example
   `feat/42-user-authentication`); see "Branch naming" above.
3. Put `Closes #<N>` in the PR body so the issue closes when the PR merges.

Then:

- Keep PRs focused: one logical change per PR.
- All CI checks must pass before merging.
- Direct commits to `main` are not allowed.

### PRs closed without merging

`delete_branch_on_merge` never fires for a PR **closed unmerged**, so its branch would pile up on
`origin`. `delete-closed-pr-branch.yml` deletes the head branch of a same-repository PR closed
without merge, and only when every guard holds; a skipped branch is named with its reason in the
job summary:

- the PR is from this repository, never a fork;
- the branch is short-lived, matching `<type>/<N>-<slug>`, so `develop`, `release/*`,
  `dependabot/*` and `renovate/*` are never touched;
- it is not the default branch and not the PR's own base branch;
- no other open PR uses it as its base or its head (a stacked PR or a second PR from the same head
  would be closed by the deletion); an unreadable answer counts as "in use";
- GitHub reports it as not protected, and an unreadable protection state counts as protected;
- its name uses only letters, digits and `._/-`, and its tip is still the PR head when read just
  before the delete.

The checks and the delete are separate API calls and the refs API has no compare-and-delete, so a
push in that gap is covered only by the restore path.

Nothing is lost: the job summary names the deleted ref and its sha, and the PR page offers
**Restore branch** (or, from a clone that holds the commit,
`git push origin <sha>:refs/heads/<branch>`). A PR whose branch was deleted can only be reopened
after **Restore branch**. A ruleset refusal is reported as "kept" (green); any other unexpected API
error fails the job. GitHub does not run `pull_request` workflows while a PR has a merge conflict,
so a conflicted PR closed unmerged keeps its branch; delete it by hand.
