# Complexity ceilings: measured, not copied (blueprintx#425)

`templates/python-common/bin/check_complexity.sh` enforces a cyclomatic-complexity ceiling
that differs by tree — **1** for `tests/`, **2** for `src/`, **8** for `bin/` — via ruff's
`C901` (mccabe). `templates/react-spa-webpack/eslint.config.js` enforces the TypeScript
sibling — **3** for `src/**/*.{ts,tsx}`, **2** for test files — via ESLint's built-in
`complexity` rule.

This page exists because one question about that pair is reasonable, recurring, and was
never written down: *"radon gives an A up to complexity 5 — why is our ceiling 2?"* The
short answer is that **`ruff C901` and `radon`'s cyclomatic-complexity metric count
different things under the same name** — a radon grade cannot be used to justify or
challenge a ruff ceiling — and this page is the measurement backing that answer, not an
assertion of it.

## Confirmed not already written up

Before adding this page, two checks ran to confirm the question was open:

**1. No merged PR already closes #425.** GraphQL search over
`repo:guilhermegor/blueprintx is:pr 425 in:body` (deliberately without `is:open`, so a
merged PR would still surface):

```graphql
{
  search(query: "repo:guilhermegor/blueprintx is:pr 425 in:body", type: ISSUE, first: 20) {
    nodes {
      ... on PullRequest {
        number title state
        closingIssuesReferences(first: 10) { nodes { number } }
      }
    }
  }
}
```

Result: one PR matched the text search (`#443`), and its `closingIssuesReferences` names
`#439`, not `#425`. No PR — open or merged — closes #425 today.

**2. `CONTRIBUTING.md` and `CLAUDE.md` state the *rule* (parity is by construct, and the
same digit means different things in ruff vs ESLint) but neither carries the *per-construct
table* this issue asks for.** `CONTRIBUTING.md`'s "Cross-Language Quality Parity" section
already says:

> `complexity: 2` in ESLint is *more* severe than `max-complexity = 2` in ruff, because
> ESLint's cyclomatic-complexity counter counts `&&`/`||` short-circuit branches and ruff's
> mccabe engine does not (blueprintx#425).

`CLAUDE.md`'s complexity-gate paragraph states the per-tree ceilings and the reason they
differ by tree, and separately warns that a hand-rolled counter treating `assert`/`with` as
decision points measured 85% of `tests/` violating against a real figure of 8% — but neither
file shows the raw per-construct numbers below. This page is that missing table, kept out of
both held files per the collision constraint on this branch.

## What enforces the ceilings today

- `templates/python-common/bin/check_complexity.sh` — `DICT_MAX_COMPLEXITY = {tests: 1,
  src: 2, bin: 8}`, one `ruff check --select C901 --config lint.mccabe.max-complexity=<n>`
  invocation per tree (a per-file-ignore can turn `C901` off for a path but cannot give it a
  different ceiling, hence two invocations rather than one config).
- `templates/python-common/ruff.toml` — `C901` reaches the tree via `select` (`"PL"` does not
  imply mccabe; it is `select`ed independently), no `[lint.mccabe]` override at the repo
  level (the ceiling is passed on the CLI by the gate script above, not declared in the TOML).
- `templates/react-spa-webpack/eslint.config.js` — `complexity: ['error', 3]` for
  `src/**/*.{ts,tsx}`, `complexity: ['error', 2]` for `**/*.{test,spec}.{ts,tsx,js,jsx}`,
  both already measured against the scaffolded example capability (documented inline: at 2,
  16% of `src/` functions violate — not a payable number; at 3, zero do).

## Measurement technique: ceiling 0 reads back the tool's own number

The reusable trick, used both here and previously for the ESLint side (`react-spa-webpack`
CLAUDE.md, "Cyclomatic complexity" section): set the ceiling to **0**. Every function then
violates, and the reported `(N > 0)` **is** the tool's real per-function figure in its own
scale — never inferred from documentation, never carried over from a different tool.

```bash
ruff check <file> --select C901 \
  --config templates/python-common/ruff.toml \
  --config "lint.mccabe.max-complexity = 0" \
  --output-format concise --no-cache
```

## Measured table (2026-09-13, ruff 0.11.13, same command as above)

A probe file with one function per construct, run through the command above:

| construct | ruff `C901` | passes `src` = 2? |
|---|---|---|
| `if a > 0 and b > 0` (one `and`, one branch) | **2** | yes |
| `if a > 0 or b > 0 or c > 0` (two `or`s, one branch) | **2** | yes |
| `try` / `except` | 2 | yes |
| `if` inside `for` | **3** | no |
| `if` nested inside `if` | 3 | no |
| function with only `assert` statements | **1** | yes |
| `with` + `assert` | **1** | yes |

This reproduces every row of the issue's original table exactly, plus one new data point:
chaining a *second* `or` (three operands, still one branch) still reports **2**, not 3 —
confirming the boolean-operator count itself, not just its presence, is invisible to ruff's
mccabe implementation. Radon's published algorithm counts each boolean operator as its own
decision point (the classic McCabe formula extension), which is why the two tools diverge —
but no radon number is reported on this page: radon is not an installed dependency of this
repo (`pip show radon` → not found) and this repo does not add a dependency solely to
produce one comparison figure. The claim that radon counts `and`/`or` and ruff does not is a
documented, structural difference between the two implementations, not a numeric claim
requiring reproduction here.

## The two conclusions that invert the intuition

1. **`and` / `or` do not raise the mccabe count in ruff.** `if a and b` passes `src` = 2. The
   worry that the ceiling forbids a composite condition was unfounded — it doesn't, at any
   chain length.
2. **`assert` does not raise it either.** A test function with three asserts and a `with`
   stays at 1. The `tests/` ceiling of 1 does what it was built to do — forbid a *branch* —
   without penalizing assertion count.

The one real constraint `src` = 2 imposes is `if` inside `for` (or nested `if`), which reports
3 and fails. The fix is to extract — a filtered `for` becomes a comprehension, or the body
becomes its own function — not to raise the ceiling. If that extraction is later measured to
produce worse functions than the branch it replaces, that is a new issue with its own
measurement of how many functions the new ceiling would free, not an argument from radon's
scale.

## Related

- `CONTRIBUTING.md` → "Cross-Language Quality Parity" — the general rule this page backs
  with numbers.
- `templates/python-common/bin/check_complexity.sh` — the enforcement, with its own per-tree
  rationale in its header comment.
- `templates/react-spa-webpack/eslint.config.js` / its `CLAUDE.md` "Cyclomatic complexity"
  section — the TypeScript side (blueprintx#168), independently measured rather than copied
  by symmetry.
- blueprintx#425 — this issue.
