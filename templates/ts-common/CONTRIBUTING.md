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

## Pull requests

- Keep PRs focused: one logical change per PR.
- All CI checks must pass before merging.
- Direct commits to `main` are not allowed.
