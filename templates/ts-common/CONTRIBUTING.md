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
- Functions are capped at 60 lines (100 for a `.tsx`/`.jsx` component body) via
  `max-lines-per-function`, and catch clauses must narrow before use — see
  `CLAUDE.md`'s "Function length" / "Catch safety" sections for the reasoning

## Pull requests

- Keep PRs focused: one logical change per PR.
- All CI checks must pass before merging.
- Direct commits to `main` are not allowed.
