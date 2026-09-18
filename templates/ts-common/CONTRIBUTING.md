# Contributing

## Branch naming

| Type | Pattern |
|------|---------|
| Feature | `feat/<short-description>` |
| Bug fix | `fix/<short-description>` |
| Docs | `docs/<short-description>` |
| Refactor | `refactor/<short-description>` |
| Chore | `chore/<short-description>` |

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

## Pull requests

- Keep PRs focused: one logical change per PR.
- All CI checks must pass before merging.
- Direct commits to `main` are not allowed.
