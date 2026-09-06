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

## Pull Request Process

1. **Create an Issue First**:
   - Check existing issues at [GitHub Issues](https://github.com/guilhermegor/blueprintx/issues)
   - Open a new issue if none exists for your work

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

## Ruff Rule Adoption Log

`templates/python-common/ruff.toml` only carries a short pointer comment beside each
rule-set entry in `[lint].select` — the full measurement and, where a rule needed a
case-by-case call, the reasoning for each finding lives here.

### `RET` (flake8-return) — blueprintx#426

Adopted whole, including `RET501` (a `return None` that duplicates the function's
implicit `None`) — not narrowed to only `RET505` (the "unnecessary `else` after
`return`" early-return check).

- **`RET505` and the rest of the family:** 0 findings measured across
  `src/ bin/ tests/ optional/` — the codebase already writes early returns
  everywhere. Adopting it is a zero-cost regression gate: it does not rewrite any
  existing code, it only stops a future `if: return … else: return …` shape from
  landing.
- **`RET501`:** 5 findings, all the same shape — a `close()` method (or, in one
  case, an async `__aexit__`/a YAML-loader callback) annotated `-> None` whose body
  ends in an explicit `return None`. In every one of the 5, `None` is the
  function's *only* possible return value (per the rule's own message,
  "if it is the only possible return value") — none of them is a `-> X | None`
  function where a mid-function `return None` is a deliberate distinct outcome
  the caller consumes. All 5 were therefore residue and the line was deleted
  (never suppressed with `# noqa`):
  - `bin/check_docs_sections.py::_ignore_unknown`
  - `optional/browser_steps/tests/test_step_handlers.py::FakeDownloadInfo.__aexit__`
  - `optional/chassis/db_wschema/infrastructure/csv_handler.py::CsvHandler.close`
  - `optional/chassis/db_wschema/infrastructure/joblib_handler.py::JoblibHandler.close`
  - `optional/chassis/db_wschema/infrastructure/json_handler.py::JsonHandler.close`

  If a future `RET501` finding **is** a deliberate `None` branch of a `-> X | None`
  function (the `None` is the result the caller consumes, not leftover
  boilerplate), the right fix is a line-scoped `# noqa: RET501` **with a reason**,
  not deletion — an unreasoned `noqa` is the same debt as an unreasoned comment.

## Best Practices

- **Keep branches focused** - one feature/bugfix per branch
- **Make small, frequent commits** - easier to review
- **Write descriptive commit messages** - explain why, not just what
- **Update documentation** - when adding new features
- **Follow existing patterns** - maintain consistency
- **Communicate early** - if you're stuck or need clarification

We appreciate your contributions and look forward to collaborating with you!
