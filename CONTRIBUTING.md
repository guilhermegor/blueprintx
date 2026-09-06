# Contribution Guidelines

Thank you for considering contributing to our project! Please take a moment to review these guidelines to ensure a smooth collaboration.

## Branching Strategy

### Branch Naming Convention

All branches must follow the pattern: `<purpose>/<branch-task>`

**Available purposes:**

| Purpose         | Format                      | When to Use |
|-----------------|-----------------------------|-------------|
| Feature         | `feature/<name>` or `feat/<name>` | New functionality |
| Bugfix          | `bugfix/<description>` or `fix/<description>` | Bug resolution |
| Hotfix          | `hotfix/<description>` | Critical production fixes |
| Release         | `release/<version>` | Version preparation |
| Documentation   | `docs/<description>` | Documentation updates |
| Refactor        | `refactor/<description>` | Code improvements |
| Chore           | `chore/<description>` | Project maintenance tasks |

**Examples:**
- `feat/user-authentication`
- `fix/login-validation-issue`
- `docs/update-api-reference`

## Commit Message Standards

All commits must follow the [Conventional Commits](https://www.conventionalcommits.org/) specification: `<type>/<scope>`


**Available types:**

| Type       | Purpose |
|------------|---------|
| `build`    | Build system or dependency changes |
| `ci`       | CI configuration changes |
| `docs`     | Documentation updates |
| `feat`     | New features |
| `fix`      | Bug fixes |
| `perf`     | Performance improvements |
| `refactor` | Code restructuring |
| `style`    | Formatting changes |
| `test`     | Test additions/modifications |
| `chore`    | Maintenance tasks |
| `revert`   | Reverting changes |
| `bump`     | Version updates |

**Examples:**
- `feat(auth): implement OAuth2 integration`
- `fix(calculations): correct rounding errors in tax computation`
- `docs(readme): add installation instructions`

## Development Setup


1. **Dependency Management**:
   - Use Poetry (version specified in `requirements.txt`)
   - Avoid adding redundant libraries - check `pyproject.toml` first
   - Run `poetry install` to set up the development environment

2. **Pre-commit Hooks**:
   - Install with `make precommit_update`
   - This enables automatic:
     - Code linting
     - Formatting
     - Security vulnerability scanning
     - Large file detection
     - Secret key detection

3. **Testing Framework**:
   - Maintain the standard file structure:
     - Implementation: `src/<feat_name>.py`
     - Tests: `tests/test_<feat_name>.py`
   - Run comprehensive validation with: `poe unit_tests -k <keyword>`
        - This command executes:
            - **Ruff**: Linting, formatting, and flagging deprecated Python features
            - **Codespell**: Spelling verification in comments and docstrings
            - **Automated tests**: All test cases matching the project's testing standards
   - Ensure 100% test coverage for critical components
   - Run tests locally before pushing changes

4. **Test-Driven Development**:
   - Write tests before implementation when possible
   - Include normal operations, edge cases, error conditions, type validation, and checks for examples in docstrings
   - Maintain test fixtures for complex scenarios
   - Recommended to use UNIT_TEST_TEMPLATE.md for AI generation of unit tests, in order to implement test-driven development best practices and follow project standards

## Cross-Language Quality Parity

BlueprintX scaffolds more than one language (Python and TypeScript/JS today), and a quality
decision made only on one side quietly widens the gap between them. Two rules keep that from
happening silently:

1. **Every quality decision applies to all scaffolded languages**, unless that language's own
   community standard says otherwise — and when it does, **the community standard outranks the
   house rule**.
2. **These decisions live in `README.md` / `CONTRIBUTING.md` / `docs/`, never as a code
   comment.** The one exception is a QA-suppression comment (`noqa`, `complexity-ok`,
   `type: ignore`, `codespell:ignore` — blueprintx#303 exempts these explicitly). A config file
   (`ruff.toml`, `eslint.config.js`) may carry the rule line plus a short pointer comment; the
   long justification belongs in the docs, not inline.

**Precedence order when a house rule and a language standard conflict:**

1. The language's own community standard (PEP-8 / PEP-257 for Python, ECMAScript/TC39 for
   JS/TS, the equivalent for any language added later).
2. This repo's cross-cutting rule.
3. Style preference.

A house rule that contradicts PEP-8 is a **defect in the rule**, not in Python.

### Parity is by prohibited construct, never by number

Copying a numeric literal between two languages' linters is not parity — it can silently produce
the wrong rule on one side. Two measured examples:

- **`complexity: 2` in ESLint is *more* severe than `max-complexity = 2` in ruff**, because
  ESLint's cyclomatic-complexity counter counts `&&`/`||` short-circuit branches and ruff's
  mccabe engine does not (blueprintx#425). The same digit delivers a different rule.
- **PEP-8 requires a space around `=` when the assignment carries a type annotation
  (`x: int = 7`) and forbids one when it doesn't (`x=7`)**. A single "uniform spacing around `=`"
  rule would be wrong on both sides of that same language.

The correct parity is by *what construct is forbidden*, not by the number that enforces it: both
languages should forbid nesting and allow a composite condition, but the numbers that deliver
that differ because the two linters' scales differ — ESLint needs `max-depth` plus a loose
`complexity`, while ruff's mccabe needs only a tight `max-complexity` by itself.

### Mandatory question for new quality issues

An issue that proposes a new quality decision (a lint rule, a gate, a coding convention) must
answer, in its body, **"what is the shape of this in the other scaffolded languages?"** — even
when the honest answer is "no equivalent tool exists yet, tracked as prose, not a gate."

This is **not** a gate. "Was this decision applied to both language families?" is not
machine-decidable — it is a review question, so it stays prose reviewed by a human, never a
`bin/check_*.sh` script.

### Cross-language gate-parity snapshot (measured 2026-09-06)

| Quality gate | Python | TypeScript/JS |
|---|---|---|
| Cyclomatic-complexity ceiling | ✅ ruff `C901`, tier-scoped (1 for `tests/`, 2 for `src/`, 8 for `bin/`) — `check_complexity.sh` | ❌ none (blueprintx#168) |
| Function-length ceiling | ✅ 60 lines — `check_function_length.py` | ❌ none |
| Deny-by-default import/vendor policy | ✅ `.layer-policy.yaml` + `check_layer_imports.py` on every Python tier | 🟡 partial — `templates/ts-lib/eslint.config.mjs` has a per-layer vendor allowlist (blueprintx#345); `templates/react-spa-webpack/eslint.config.js` only has `eslint-plugin-boundaries`, which polices layer *direction*, not a vendor allowlist |
| Builtin-name shadowing | ✅ ruff `A` (blueprintx#421, closes #418) | ❌ none — no `no-shadow`/`no-redeclare` configured |
| Early-return / forbidden nesting | 🔧 in flight — ruff `RET` (blueprintx#426) | ❌ none |
| Coverage floor | ✅ `fail_under = 80` (`.coveragerc`) | ❌ no Jest `coverageThreshold` configured |

Re-measure before trusting this table on a later read — it is a snapshot, not a standing fact.
Update the date in this heading when re-measured, so the next reader knows whether the gap
narrowed or widened.

## Pull Request Process

1. **Create an Issue First**:
   - Check existing issues at [GitHub Issues](https://github.com/guilhermegor/blueprintx/issues)
   - Open a new issue if none exists for your work
   - If the issue proposes a new quality decision, answer the mandatory question above in the
     issue body before scoping the work

2. **Opening a PR**:
   - Fill out the PR template completely
   - Include:
     - Detailed description
     - Changes made
     - Testing performed
     - Documentation updates
     - Any technical debt created

3. **Code Review**:
   - Expect constructive feedback
   - Address all review comments
   - Update documentation as needed
   - Keep commits logically organized

4. **Merge Approval**:
   - Requires at least one approval
   - All tests must pass
   - Code coverage should not decrease
   - Documentation must be updated

## Best Practices

- **Keep branches focused** - one feature/bugfix per branch
- **Make small, frequent commits** - easier to review
- **Write descriptive commit messages** - explain why, not just what
- **Update documentation** - when adding new features
- **Follow existing patterns** - maintain consistency
- **Communicate early** - if you're stuck or need clarification

We appreciate your contributions and look forward to collaborating with you!
