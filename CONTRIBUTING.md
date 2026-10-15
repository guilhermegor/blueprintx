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

5. **GitGuardian exceptions**: a false positive in the secret scan is silenced in the root `.gitguardian.yaml` (`secret.ignored_matches`), never by editing history. Every entry needs a `name` stating why the match is not a credential.

6. **Template lockfiles**: a dependency change to any `templates/*/package.json` regenerates that tier's `package-lock.json` in the same commit (`npm install --package-lock-only` in a rendered copy of the tier). `bin/ci/check_lockfile_sync.sh` fails the commit and the `lockfile-sync` job otherwise; an out-of-sync lock makes `npm ci` refuse to install and turns every open PR red (#588).

## Repository Secrets (Actions)

This repo's own Actions secrets (`gh secret list`) are set by hand and reproducible from
`.env.example`, not from memory — the pattern `dotfiles-dev` uses for its own credentials.
`.env.example` (tracked) documents every secret's consumer and minimum scope; `.env`
(git-ignored, `*.env` in `.gitignore`) holds the real values. **`.env` does NOT feed CI** —
GitHub Actions cannot read it — it is only the source you `gh secret set` from.

| Secret | Consumer(s) | Minimum scope |
|---|---|---|
| `GH_PAT_REVIEW_TRIGGER` | `coderabbit_trigger.yml`, `review_retry.yml`, `verify_branch_protection.yml` | Fine-grained PAT, this repo only, `Pull requests: Read and write` + `Administration: Read` (not `Issues: write`) |
| `GITGUARDIAN_API_KEY` | `scaffold_checks.yml` (`secret-scan` job) | GitGuardian API key with the `scan` scope |
| `APT_GPG_KEY_ID` | `release_apt.yml`, `release.yml` | GPG key ID of `APT_GPG_PRIVATE_KEY` |
| `APT_GPG_PASSPHRASE` | `release_apt.yml`, `release.yml` | Passphrase for `APT_GPG_PRIVATE_KEY` |
| `APT_GPG_PRIVATE_KEY` | `release_apt.yml`, `release.yml` | Armored GPG private key that signs the APT repo |
| `SNAPCRAFT_STORE_CREDENTIALS` | `release_snap.yml`, `release.yml` | Snap Store login exported with `snapcraft export-login`; first-time setup is in `.specs/features/snap-publishing/plan.md` |

**Re-provisioning a lost/rotated value:**
1. Mint the new credential (fine-grained PAT at github.com/settings/personal-access-tokens,
   API key at the vendor, or the GPG key exported to a private file outside the work tree,
   never to the terminal: `f=$(mktemp) && gpg --export-secret-keys --armor <key-id> > "$f"`
   (`mktemp` creates it mode 600 under `/tmp`, so a stray `git add -A` cannot stage it), paste
   it into `.env`, then `shred -u "$f"`, or `rm "$f"` where `shred` is unavailable) with the
   scope from the table above, never broader. The PAT's `Issues: write` stays off: a token
   with it was measured (2026-09-10) to 403 on issues and 422 on PRs, and the workflows only
   ever comment on PRs.
2. `[ -e .env ] || install -m 600 .env.example .env; chmod 600 .env` (never overwrites a
   `.env` that already holds real values, and tightens one with loose permissions), then
   replace the `KEY-GOES-HERE` placeholder of the secret you are setting.
3. Source it in a subshell, so the variables do not outlive the command, without `set -a`, so
   they are never exported into `gh`'s environment (`printf` is a builtin, so the value still
   reaches the pipe), and upload over stdin, so the value never lands in `ps`/`/proc` argv
   (single-quote any value containing `$` so sourcing keeps it literal; a literal `'` inside
   is written `'\''`). The command refuses to upload when `.env` fails to source, when
   `<NAME>` is unset or empty, or when it still equals the placeholder, so a typo can never
   overwrite a working secret with an empty or placeholder value:
   `( . ./.env || exit 1; v=${<NAME>:?unset or empty in .env}; [ "$v" != KEY-GOES-HERE ] || { echo "<NAME> is still the placeholder" >&2; exit 1; }; printf '%s' "$v" | gh secret set <NAME> --repo guilhermegor/blueprintx )`.
   Skip `APT_GPG_PASSPHRASE` when the key has none (the workflow treats it as optional); when
   rotating from a key that had one to a key that has none, also run
   `gh secret delete APT_GPG_PASSPHRASE --repo guilhermegor/blueprintx`, so the old value is
   not left behind.
   Replacing `APT_GPG_PRIVATE_KEY` with a different key changes the public key APT users
   trust, so they must re-import it or `apt update` fails the signature check.
4. Verify: `gh secret list --repo guilhermegor/blueprintx` shows an updated timestamp for
   `<NAME>`, and the workflow that consumes it succeeds on its next run.

`.env.example` keeps placeholders only, never real values. Leave `APT_GPG_PASSPHRASE` empty
when the key has no passphrase, and never leave placeholder text there. Wrap a real value in
single quotes so `$` and backticks survive sourcing. `APT_GPG_PRIVATE_KEY` is a multi-line
armored block: keep the single quotes and paste the whole block, header and footer included;
it needs a bash-style `source`, not a strict dotenv parser. `SNAPCRAFT_STORE_CREDENTIALS` is
the file written by `snapcraft export-login credentials.txt`; the publish step fails without
it rather than exiting 0.

## Cross-Language Quality Parity

BlueprintX scaffolds more than one language (Python and TypeScript/JS today), and a quality
decision made only on one side quietly widens the gap between them. Two rules keep that from
happening silently:

1. **Every quality decision applies to all scaffolded languages**, unless that language's own
   community standard says otherwise — and when it does, **the community standard outranks the
   house rule**.
2. **These decisions live in `README.md` / `CONTRIBUTING.md` / `docs/`, never as a code
   comment.** The one exception is a QA-suppression comment (`noqa`, `complexity-ok`,
   `type: ignore`, `codespell:ignore` — blueprintx#303 exempts these explicitly). No pointer is
   left behind either: every comment rots, so `check_comment_budget.py` refuses any comment
   outside `comment_budget_allowlist.txt`, ratcheted down from `comment_budget_baseline.txt`
   (blueprintx#304).

   The gate reads every file type that can carry a comment, not only code: dotfiles
   (`.gitignore`, `.codespellrc`, `.editorconfig`, `.gitlint`), `Dockerfile*`, `.env.example`,
   `.conf`/`.cfg`, SQL and CSS. The local `.env` is never read. The first baseline row,
   `scope <n>`, records which file types the run that wrote it discovered: when a change
   widens discovery, rows for the newly read types are not counted as a raise against a base
   written under the older scope, while every listed row still cannot go up.

   Heredoc bodies (`<<EOF`, `<<'EOF'`, `<<-EOF`, Ruby `<<~EOS`) are data a script writes out,
   so the gate never counts their lines as comments; a shebang inside one is output.

   `.env.example` carries keys and example values only. Each tier documents its variables in
   `docs/configuration.md`, one table row per variable, and
   `templates/python-common/bin/check_env_docs_sync.py` fails when the file's keys and the
   rows marked `yes` in the `In .env.example` column differ in either direction. A variable
   left out of the file on purpose (`DB_PORT`) gets a `no` row.

**The rules themselves live in `quality-rules.yaml` at the repo root** (blueprintx#432) — one
entry per rule, with its per-language `tool`/`rule` (or an explicit `status: not-implemented` /
`overridden_by:`), validated by `templates/python-common/bin/check_quality_rules.py` so the
table cannot silently drift from the config it describes. The *reason* behind each entry lives
in [`docs/quality-rules.md`](docs/quality-rules.md); a new rule enters both, never just one.

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
languages should forbid nesting and allow a composite condition, but the rules that deliver that
differ, because **neither linter's complexity rule can see nesting at all**.

⚠️ Ruff `C901` and ESLint `complexity` both measure **McCabe cyclomatic complexity** — a count of
decision points, blind to how they are arranged. ESLint `max-depth` measures **nested block
depth**, a different property. Measured witness, two functions with three `if`s each:

| function | shape | ruff `C901` | ruff `PLR1702` |
|---|---|---|---|
| three sequential `if`s | depth 1 | `is too complex (4 > 2)` | not flagged |
| three nested `if`s | depth 3 | `is too complex (4 > 2)` | `Too many nested blocks (3 > 1)` |

**The same number, 4, for opposite shapes.** So a tight `max-complexity` does not enforce the
nesting rule — it forbids a superset, rejecting the flat early-return form this project prefers
for exactly the complexity it is trying to reduce.

Python's nesting-specific rule is `PLR1702` (`too-many-nested-blocks`), and it is ⚠️ **not
configured today**: ruff gates it behind `--preview`, which `templates/python-common/ruff.toml`
does not enable, so selecting `PL` does not activate it (`warning: Selection PLR1702 has no
effect because preview is not enabled`). Until blueprintx#434 lands, **the Python and TypeScript
nesting policies are approximate, not equivalent** — Python bounds nesting only as a side effect
of bounding complexity.

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
| Early-return shape | 🔧 in flight — ruff `RET` (blueprintx#426) | ❌ none |
| Nesting-depth ceiling | ❌ none — `PLR1702` is preview-gated and preview is off (blueprintx#434); `C901` bounds nesting only as a side effect | ❌ none — no `max-depth` |
| Coverage floor | ✅ `fail_under = 80` (`.coveragerc`) | ❌ no Jest `coverageThreshold` configured |
| Casing convention (functions/variables/import aliases) — row re-measured 2026-09-13 | ✅ ruff `N`, minus `N802` in `tests/**` (blueprintx#422, closes #422) | ❌ none configured — `@typescript-eslint/naming-convention` exists but is unused. No like-for-like gap: a JS/TS test name is a **string literal** passed to `it()`/`describe()`, not a function identifier, so the one real N802 collision this issue measured (a test name using upper-case for semantic emphasis) has no TS equivalent to conflict with in the first place. TypeScript also has no analogue to the type-prefix convention that would otherwise fight a constant-casing rule — this repo's Python house convention is Python-only |
| Broad-except / catch-safety | ✅ ruff `BLE` (blueprintx#440) on top of the already-selected `E722`/`S110` | ✅ `@typescript-eslint/use-unknown-in-catch-callback-variable` + `only-throw-error` (blueprintx#440/#443) — by construction, not transcription: JS has no typed catch clause to mirror `BLE`, so the TS side closes the one gap `strict: true`'s `useUnknownInCatchVariables` leaves open (`.catch(cb)` callbacks) instead |
| Required status checks provisioned on the default branch — row added 2026-09-20 | ✅ `bin/enable_repo_rules.sh` seeds `REQUIRED_CHECKS=("Review threads answered")` and provisions the `pr-quality-gate` ruleset from it | ❌ none — the script ships only from `templates/python-common/`, so the check names `ts-common`/`ts-lib` emit (`webpack`, `eslint`, `stylelint`, `jest`, `type-check`, `Review threads answered`) are required by nothing. Same for the `bash-cli` tier, which additionally ships no review-threads workflow at all (blueprintx#164; per-tier inventory and the four-rule qualification test in `docs/required-status-checks.md`) |

Re-measure before trusting this table on a later read — it is a snapshot, not a standing fact.
The heading date covers the table as a whole; a row re-measured later carries its own date in
its first cell, so one fresh row never implies the other rows were re-measured with it.
Update the date in this heading when the WHOLE table is re-measured, so the next reader knows whether the gap
narrowed or widened.

### TypeScript build + lint gate

The `typecheck-ts` CI job (`.github/workflows/scaffold_checks.yml`) scaffolds `react-spa-webpack`
and `ts-lib` for real, then runs `type-check`, `build`, `lint:css` and `lint` in the generated
project (#726). It replaced a hand-assembled workspace that ran only `tsc --noEmit`: that copy
drifted from the scaffold (#436) and could not see webpack, stylelint or eslint, so a
`ts-common` dependency bump that broke the build merged green.

- **Stdin is `/dev/null`.** Every scaffold prompt reads with `|| true` and falls back to its
  default (no remote, no opt-ins), measured byte-identical to answering `n`; a prompt with no
  default fails fast on EOF instead of looping until the job timeout.
- **Install is `npm ci`** for both skeletons, from the lockfile each ships (`ts-lib`'s since #735).
- **No required check.** Only `Review threads answered` is required by the `pr-quality-gate`
  ruleset, so the job's display name can change without orphaning a branch rule.

### Rules scoped to BlueprintX, not inherited by scaffolds

Parity is the default, and it is about **languages**, not about the BlueprintX/generated-project
boundary. A few rules govern how *this repository* is written and deliberately stop at the edge
of `templates/`. When that is the answer, it is written down here — "we chose not to" has to be
as visible as "we did", or the next reader re-opens a settled question as if it were an
oversight.

| Rule | Scope | Why it stops here |
|---|---|---|
| **Prose language is en-US** (blueprintx#194) | BlueprintX's own prose | A generated project may legitimately be bilingual. `templates/python-common/bin/check_comment_language.py` is locale-agnostic *by design* — that is a feature of the shipped gate, not an omission. |
| **The `docs/` boundary** — `bin/ci/check_docs_boundary.sh` (blueprintx#536, scoped by #576) | BlueprintX's own `docs/` | Two reasons, and either alone would be enough. **(1)** The same path means opposite things on the two sides: `docs/backlog/` at this root is the violation the rule names, while inside `templates/<tier>/` it is a shipped product surface with its own gate (`templates/python-common/bin/check_backlog_ledger.py`, wired into that tier's pre-commit + CI), present in five tiers today — `ddd-service-native-db`, `ddd-service-orm-db`, `mvc-service-native-db`, `mvc-service-orm-db`, `lib-minimal`. A guard that cannot tell them apart is worse than no guard: it condemns a feature the repo deliberately ships. **(2)** A generated project's `docs/` answers to its own authors, exactly as its prose language does. |

Two consequences worth stating, because both were live options that were rejected:

- **No carve-out.** "Walk `templates/*/docs/` with `backlog/` exempted" was option (a) and would
  make BlueprintX the authority over a downstream project's `docs/` layout, for the sake of a
  rule the downstream project never agreed to. The carve-out list would then have to track every
  directory a skeleton legitimately ships — a second, drifting copy of the skeletons' contents.
- **No opt-in knob.** A configurable boundary the generated project inherits was option (c), and
  `check_docs_boundary.sh` therefore takes **no `--root` flag**, unlike the rest of the gate
  family. Under this decision there is only ever one tree to walk. A knob nothing turns is an
  invitation to widen the scope without re-deciding it, and the widening would be invisible in
  review as a one-word config change.

`tests/test_check_docs_boundary.sh` asserts the scope
(`test_templates_tree_is_deliberately_not_walked`): a planted violation under
`templates/<tier>/docs/`, alongside a tier's real `docs/backlog/`, must leave the gate green.
Re-pointing the gate at `templates/` turns that case red rather than quietly failing the repo
for a feature it ships.

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

### PR file-count ceiling — blueprintx#551

A PR is capped at **90 cumulative changed files**, enforced by `bin/ci/check_pr_file_count.py`
in both pre-commit and CI (`pr-file-count` job). Above it, split at a natural seam — by
capability/tier, or whitespace-only vs content-changed — into PRs of 90 files or fewer each.

The number is measured, not chosen: CodeRabbit hard-refuses to review a PR above **100**
changed files (`Review skipped: N files exceed the limit of 100`), and a PR in that state can
never merge. Over the 100 most recent PRs, exactly **1** exceeded even 90 files, and the
largest legitimate PR in that set was 59 files — so 90 leaves headroom on both sides without
being a rule nobody pays.

### PR template layout — blueprintx#587

`bin/ci/check_pr_template.sh` checks a PR body against the layout
`.github/PULL_REQUEST_TEMPLATE.md` declares, not just its five `##` headings. It runs in CI
(the `pr-template` job in `pr_template.yml`, reading the live body from the API and re-running
when the body is edited) and its should-fail tests run in
pre-commit and CI. The contract is walked out of the template itself, so editing the template
changes what the gate enforces; only the split below is recorded in the script, because
syntax cannot say which labels are optional.

A heading or `**Label**:` must start its line (prose, fenced code and HTML comments do not
count; `**Label:**` and `**Label** :` are accepted, a list marker, indent or `> ` quote is
not), carry content, and leave none of the template's own placeholder lines in place. Fields
are matched per `##` section, so an `**Added**:` under the wrong section does not count.

| Element | Rule | Why |
|---|---|---|
| The five `##` sections, `**What**` / `**Why**` / `**How**`, `**Reviewer Focus**` | **Mandatory** | Every PR has a motivation, a mechanism and something a reviewer should look at first. |
| `**Added**` / `**Updated**` / `**Fixed**` | At least **one** filled under Changes Made | A PR changes something, but which verb applies depends on the PR; `**Fixed**` alone is only true when an issue is fixed. |
| `### Manual Testing` / `### Automated Testing` | Mandatory **unless** `**Not Applicable**` explains the gap | A docs-only change has no manual run; forcing the subsection would produce filler. |
| `**Not Applicable**` | Required **exactly when** a testing subsection is not filled in | It is the stated reason for skipping, so it is demanded only when something is skipped. |
| `**Dependencies**` / `**Follow-up**` | **Optional**, may be deleted | Most PRs have neither; requiring them yields text that looks answered and is not. Left as the template text, they fail. |

Bot authors (`dependabot[bot]` and any other `[bot]` login) are exempt: they create PRs
server-side and cannot write prose fields, and an unfixable red teaches everyone to ignore the
gate. The local `pr_template_guard.sh` hook stays as the fast pre-flight; CI covers the PRs it
cannot see (the web UI, Dependabot, API-created PRs).

The job is **not yet a required check**. As with #507 and #535, it becomes one once the open-PR
population is clean, because requiring a gate that most open PRs fail blocks them all at once.

### Required checks and the allowlist of optional ones — blueprintx#535

A required check is matched by name, so `bin/ci/check_required_checks_sync.py` fails when a
required context has no job behind it, or when a job that runs on every PR is neither required
nor listed in `bin/ci/required_checks_policy.txt` with a one-line reason. Adding a PR job means
requiring it or allowlisting it in the same PR. Details: `docs/required-status-checks.md`.

### GitHub Actions are pinned by commit SHA — blueprintx#369

Every remote action reference in a workflow — first-party `actions/*` included — is pinned to
the full 40-character commit SHA of a released tag, with that tag as a trailing comment:

```yaml
- uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262 # v4.4.0
```

Enforced by `bin/ci/check_actions.sh` (`check_action_pins`) over every workflow shipped in
`templates/`, in both pre-commit (`lint-actions`) and CI. A tag reference, a branch reference,
a short SHA, or a SHA without the version comment all fail naming the file and line;
`tests/test_check_actions_pins.sh` is the should-fail witness for each shape.

Why the SHA and not the tag: a tag is a movable pointer. If `v4` moves — by compromise or a
maintainer force-push — the workflow runs different code with no diff in the repo and no
signal anywhere. The sharpest case is `secret_scan.yaml`, which runs `checkout` before
`gitleaks`: a moved tag rewrites the workspace before the scanner reads it. `actions/*` is
not exempt, because `actions/cache@v3` — a version GitHub stopped running — already sat in
three tiers until `check_actions.sh`'s first run found it: the org being trusted is not the
same as the reference being stable.

Why the trailing `# vX.Y.Z` is mandatory, not decoration: pinning alone stops security patches
arriving. Dependabot's `github-actions` ecosystem (already configured in
`templates/python-common/.github/dependabot.yml` and this repo's own) reads that comment to
know which version a SHA stands for, and rewrites both SHA and comment when it bumps. A bare
SHA is a pin Dependabot cannot update — worse than the tag it replaced.

Measured 2026-09-20 when the rule was adopted: **83 references across 25 template workflows,
12 distinct `action@tag` pairs, 0 pinned**. Resolve a new SHA from the real tag
(`git ls-remote --tags https://github.com/<owner>/<repo>` shows the peeled `^{}` commit of an
annotated tag), never from memory or another repo's copy.

## Ruff Rule Adoption Log

`templates/python-common/ruff.toml` carries no comment beside the
rule-set entries in `[lint].select`; the full measurement and, where a rule needed a
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
- **`RET501`:** 5 findings in `templates/python-common` (the scope the original
  measurement covered), all the same shape — a `close()` method (or, in one case,
  an async `__aexit__`/a YAML-loader callback) annotated `-> None` whose body ends
  in an explicit `return None`. **`bin/ci/scaffold_lint_test.sh` then surfaced 6
  more** in `templates/ddd-service-native-db/src/chassis/db_schema/infrastructure/`
  (one per SQL backend's `close()`) — a skeleton-owned tree `ruff check` from
  `templates/python-common` never reaches, so the original measurement could not
  see them; only running `poe lint` inside a real scaffolded project could. In
  every one of the 11, `None` is the function's *only* possible return value (per
  the rule's own message, "if it is the only possible return value") — none of
  them is a `-> X | None` function where a mid-function `return None` is a
  deliberate distinct outcome the caller consumes. All 11 were therefore residue
  and the line was deleted (never suppressed with `# noqa`):
  - `templates/python-common/bin/check_docs_sections.py::_ignore_unknown`
  - `templates/python-common/optional/browser_steps/tests/test_step_handlers.py::FakeDownloadInfo.__aexit__`
  - `templates/python-common/optional/chassis/db_wschema/infrastructure/csv_handler.py::CsvHandler.close`
  - `templates/python-common/optional/chassis/db_wschema/infrastructure/joblib_handler.py::JoblibHandler.close`
  - `templates/python-common/optional/chassis/db_wschema/infrastructure/json_handler.py::JsonHandler.close`
  - `templates/ddd-service-native-db/src/chassis/db_schema/infrastructure/{mariadb,mssql,mysql,oracle,postgres,sqlite}_handler.py::*Handler.close`

  If a future `RET501` finding **is** a deliberate `None` branch of a `-> X | None`
  function (the `None` is the result the caller consumes, not leftover
  boilerplate), the right fix is a line-scoped `# noqa: RET501` **with a reason**,
  not deletion — an unreasoned `noqa` is the same debt as an unreasoned comment.

### `N` (pep8-naming) — blueprintx#422

Adopted with two per-file-ignores, not whole. Re-measured 2026-09-13 (ruff 0.11.13):
`ruff check --select N --statistics src/ bin/ tests/ optional/` → 9 findings across 3
rules (an earlier count in the issue read 6 — stale; re-measuring is what the issue asked
for, not trusting the number it opened with).

- **`N802` (function name should be lowercase) — 5 findings, all false positives, ignored
  in `tests/**` only.** Every one is a test name that uses upper-case for **semantic
  emphasis** on the exact behaviour under test:
  `test_modules_with_no_policy_file_FAIL_rather_than_pass_silently`,
  `test_a_glob_governs_packages_NESTED_below_the_sublayer`,
  `test_a_dotted_deny_also_catches_the_RELATIVE_form`,
  `test_account_blocked_until_takes_the_LATEST_deadline_not_the_latest_notice`,
  `test_no_threads_is_not_a_THREAD_problem`. `tests/CLAUDE.md` asks a test name to
  describe the *behaviour*, not the function under test — the upper-case word is that
  description, not a casing slip. Renaming to satisfy N802 would erase the one thing the
  name is for. `N802` stays active everywhere else; only `tests/**` is exempt.
- **`N806` (non-lowercase variable in function) — 3 findings, all true positives, fixed by
  moving the constant to module scope.** All three are the same shape: a local `_ALL_CAPS`
  name assigned inside a function body — exactly PEP-8's "constants are module-level and
  upper-case" rule seen from the other side, since a local variable that *looks* like a
  constant is really just a plain variable wearing constant casing.
  `bin/check_assertion_weakening.py::changed_paths` (`_INT_MIN_FIELDS`) and
  `::_compare_call` (`_MIN_EQ_ARGS`), plus `bin/check_gate_integrity.py::changed_paths`
  (`_INT_MIN_FIELDS`, a near-duplicate of the first — same shape, separate file, out of
  scope for this issue). Fixed by hoisting each to a module-level `_NAME = value` beside
  the file's existing module constants; no behaviour change.
- **`N813` (camelcase module imported as lowercase) — 1 finding, evaluated and kept via a
  per-file-ignore.** `src/utils/xml_reader.py` imports `defusedxml.ElementTree as
  defused_et`. The lowercase alias is deliberate, not accidental: the file's own module
  docstring already states why `defusedxml`, not stdlib `xml.etree.ElementTree`, is the
  trust-boundary-safe parser, and the alias's job is to read as "the defused one" at every
  call site. Renaming it to satisfy N813 (e.g. `DefusedElementTree`) would only make that
  signal harder to read for no defect fixed, so this one file is ignored for `N813` rather
  than renamed.

See the cross-language parity table above for the TypeScript side of this decision — no
like-for-like gap, since a JS/TS test name is a string literal, not a function identifier.
### `BLE` (flake8-blind-except) — blueprintx#440

Closes the gap `E722` (bare `except:`, already selected via `E`) leaves open:
`except Exception:` / `except BaseException:` names a type but says nothing —
the same class of finding, one layer narrower.

- Measured 2026-09-16 (ruff 0.11.13): `ruff check --select BLE --statistics
  templates/` → 2 findings, both the SAME line in `_pipeline.py`
  (mvc-service-native-db and mvc-service-orm-db ship byte-identical files) — a
  documented five-mode degradation (`PipelineOrchestrator._enrich`) where
  splitting the `except` by mode would re-create the original defect (one
  clause remembered, the rest silently fall through). Fixed with `# noqa:
  BLE001` pointing at the method's own docstring rather than duplicating the
  five-mode rationale in a second place.
- 9 other broad handlers in the tree already carried a `# noqa: BLE001`
  comment that this rule was not yet selected to enforce — a suppression
  naming a rule that never runs looks identical to one that does, from
  either side. Selecting `BLE` is what makes those 9 pre-existing
  suppressions real.
- **`RUF` was measured in the same pass and NOT adopted.** `ruff check
  --select RUF --statistics templates/` → 150 findings (138 `RUF100`
  unused-noqa alone, mostly noqa comments anticipating rule families not yet
  selected — e.g. `N-` ahead of blueprintx#486 — plus 5 `RUF022`, 4 `RUF046`,
  3 unicode-ambiguity findings). Unlike `BLE`, this is real cost, not zero,
  so it is a deliberate separate decision rather than bundled into this
  issue: left for a follow-up issue to adopt (or narrow) on its own measured
  merits.

### TypeScript catch-safety — blueprintx#440 (already shipped, blueprintx#443)

JavaScript has no typed catch clause — there is one `catch (err)` per `try`
and no `catch (e: TypeError)` to require, so `BLE`'s rule cannot be
transcribed; parity here is by **intent** ("never handle what you cannot
identify, never swallow it"), not by construct. `templates/react-spa-webpack/
eslint.config.js` and `templates/ts-lib/eslint.config.mjs` already carry the
two type-aware rules that close the one gap plain `strict: true`
(`useUnknownInCatchVariables`) leaves open — a promise `.catch(cb)`
callback's parameter stays `any` even under strict mode:

- `@typescript-eslint/use-unknown-in-catch-callback-variable` — forces the
  same `unknown`-and-narrow discipline onto `.catch(cb)` callbacks.
- `@typescript-eslint/only-throw-error` — only `Error` values may be thrown,
  so a catch's `instanceof Error` narrowing can actually succeed.

Measured 2026-09-16: 4 `catch (err)` sites across both tiers' `src/`
(`react-spa-webpack`'s `use-cases.ts` + `use-cases.zustand.ts`, 2 each), no
`.catch(cb)` callbacks and no non-`Error` `throw` — both rules cost zero
findings today, same as the Python side.

## Migrating a generated project from `docs/backlog/` to `.specs/backlog/`

Scaffolds are generated once and never re-synced, so this applies only to a project that
hand-copies the updated template files. Before adopting the new `mkdocs.yml` and
`check_backlog_ledger.py`:

1. Move `docs/backlog/*.md` to `.specs/backlog/` (names are unchanged). Until then the old
   ledgers are not recognized by the gate, and with `backlog/` gone from `exclude_docs` they
   would be published. The tier `mkdocs.yml` files set `validation.nav.omitted_files: warn`, so
   a forgotten legacy page raises a warning that names the file. It fails only a build run
   with `mkdocs build --strict`, which no generated-project step does today.
2. Change any uppercase `[X]` marker to `[x]`, and give every `[~]` a `<type>/<branch>`; the
   ledger gate now shares the grammar of `check_specs_structure.sh`.
3. A branch already in flight with an old-path ledger needs it moved too; there is no
   transitional acceptance.

## Repository tooling notes

Configuration files in this repository carry no comments, so the reasoning lives here.

- **`.cz.toml`.** Commitizen configuration moved out of `pyproject.toml` in #233: the root
  manifest is docs-only, and the file name matches the one shipped to every generated Python
  project. Losing it does not error: `cz` falls back to defaults and exits 0 (`cz version
  --project` prints "No project information in this project."), so the symptom is an
  unprefixed tag and a different changelog format, not a red check. `version_provider =
  "poetry"` locates the manifest by project root, and that value is the `0.0.0` stub that
  `bin/ci/check_version_sync.sh` pins; the real version is the git tag. Releases are cut by
  tagging, and `cz changelog` (`make changelog`) groups commits by tag into the root
  `CHANGELOG.md`, which the docs Changelog page includes. Never hand-edit that file.
- **`pyproject.toml`** is a stub that exists to drive the docs site; do not hand-bump it.
- **`.gitlint`.** Commitizen enforces the Conventional Commits format at `commit-msg`;
  gitlint owns the length limits, written out so the contract is explicit.
- **`.codespellrc`.** `*-lessons.md` is skipped because the capture workflow writes
  git-ignored lessons mirrors under `.specs/_lessons/` and codespell scans the whole tree;
  the glob matches the basename because a `docs/`-anchored pattern fails under
  `codespell .`. Write every `ignore-words-list` entry in lowercase: codespell lowercases the
  word before lookup, so a capitalised entry matches only itself. Each surviving entry was
  measured (#197): remove it, run `codespell docs/ templates/ --config=.codespellrc`, and
  keep it only if that produces a finding. The list must stay in sync with
  `templates/python-common/.codespellrc` (`check_codespell_sync.sh`), because the two drifted
  in both directions and the stale copy was the one that ships.
- **`.gitleaks.toml`.** Scans this repository's own history, separate from the config shipped
  to generated projects. It extends the default ruleset and adds only narrow allowlists for
  measured false positives. The model-identifier allowlist uses `regexTarget = "match"` and
  an anchored regex ending in `\W*`: the match carries the closing delimiter, which is a
  double quote in Python but a backtick in the markdown ledgers, and an unanchored form also
  silenced any longer finding containing the string (a high-entropy token wrapped around it
  scored 1 finding without the allowlist and 0 with the unanchored one).
- **`.gitignore`.** Generated from the toptal Python template, plus: template paths under
  `templates/` must always be tracked even where they match general Python patterns;
  `.claude/` runtime files are ignored except `release.conf`, which declares the shipped
  paths for the release tooling, so the negation must follow the directory ignore; the
  generated lessons mirror directory is ignored as a whole so a new store cannot arrive
  untracked; the generated changelog is regenerated and never committed.
- **`.pre-commit-config.yaml`.** A local mirror of Scaffold Checks CI, separate from the
  pre-commit that ships to generated projects. Repo-local hooks call the same `bin/ci/*.sh`
  scripts as CI, so there is no drift. `default_stages: [pre-commit]` is required: without it
  a hook with no `stages:` also runs at `commit-msg`, doubling `mkdocs build --strict` and
  the codespell scan on every commit (#158). The large-file cap is 1000 KB because the
  committed lockfiles are real (`ts-common` about 596 KB, `ts-lib` about 908 KB). JSONC
  files (`.vscode/`, `tsconfig*`) skip the strict JSON parser, and `--unsafe` on the YAML
  check admits workflow `!reference` tags. Layers: generic hygiene, then Conventional Commits
  at `commit-msg`, then the shared gates. Gates that run over this repo with `--root .`
  follow the one-implementation rule; diff-scoped gates (`gate-integrity`, the PR file-count
  ceiling) compare against `merge-base(HEAD, main)` because they check a delta. The
  complexity gate runs twice, the second time scoped to `templates/python-common`, which
  catches a template defect in about 3 seconds instead of in a five-tier CI matrix (measured on
  the two issues 270 and 271). Function length is not duplicated, since its discovery already walks the whole root.
- **`quality-rules.yaml`.** Machine-readable registry of the quality rules, validated by
  `templates/python-common/bin/check_quality_rules.py`; the reasoning per rule is in
  `docs/quality-rules.md`. YAML because it needs comments (#432). Each rule has `id` (a
  stable slug, also the docs anchor), `intent` (the construct prohibited or required, never a
  number, so a Python ceiling of 2 and a TypeScript ceiling of 3 satisfy one intent, #425),
  `docs` (an anchor that must resolve to a real heading) and one block per language a
  `skeleton.meta` declares. Omission is forbidden (#430): a language without an
  implementation says `status: not-implemented`, or `overridden_by: <standard>`, both with a
  `note`. Optional `file` and `pattern` make the gate grep a plain substring in the real tool
  config, so drift is caught.
- **`.review-bots.yaml`.** The reviewer roster `check_review_threads.py` reads; the gate's
  logic names no tool, so swapping a reviewer is a row here. Reviewer shapes differ: some
  post inline threads, some only a status check. `posts:` is required on every row and
  decides more than authorship (#218): a `posts: status` member is excluded from the
  missing-review gate too, otherwise a workflow submitting a review with `GITHUB_TOKEN` would
  satisfy a gate meant to prove a real reviewer looked. A missing or misspelled `posts:`
  fails loudly, at least one `threads` member is required, and zero threads is judged against
  a submitted review, never silence (see Decision records). Delete the file to opt out.
- **`Makefile` and `tasks.sh`.** `install` runs from a clone with no `.git` at the install
  path, so it stamps the clone's `git describe` version into the installed script, matching
  the package-manager jobs. The deprecated `dev-clean`, `dry-run` and `mkdocs_server` aliases
  (#365) stay for one tagged release; the pairing gate normalises `-` and `_`, so they need no
  `tasks.sh` or `help.sh` entry. `verify_tiers` is the real check for template work: it
  scaffolds every Python tier and runs that project's lint and tests, in parallel, and
  `make lint` does not cover it (#276). `tasks.sh` translates `JOBS` to `--jobs` so both
  entry points honour it; it used to forward only positional arguments and ran at full
  concurrency while `bin/help.sh` promised serial (#277). An explicit `--jobs` wins.
- **`requirements.txt`.** The `poetry-plugin-shell` plugin restores `poetry shell`, which
  Poetry 2.x dropped. It belongs in this bootstrap install, into the interpreter Poetry runs
  from, because as a project dependency it would reach `.venv`, where no Poetry exists to
  load it.
- **`mkdocs.yml`.** `exclude_docs` keeps `superpowers/` (internal specs and plans) out of
  the built site; the snippets extension enables the Changelog page's include of the root
  file.
- **Packaging.** `Formula/blueprintx.rb` installs `bin/` and `templates/` under `libexec` so
  `SCRIPT_DIR`-based navigation resolves `BLUEPRINTX_ROOT` without patching, and its wrapper
  uses `exec` so `BASH_SOURCE` resolves to `libexec/bin`. Each package stamps the release
  version into the fallback literal, since none has a `.git`.

## Shell test suites under `tests/`

Each `tests/test_*.sh` is a should-fail regression suite for a gate or script. Shared
conventions, which the suites no longer repeat in headers:

- The dangerous direction is a **false pass**, so every refusal is asserted by the diagnostic
  that names the cause, not by a bare non-zero exit, which a crash produces too. Every rule
  also has a control case that passes: without it a gate that rejects everything satisfies
  the suite.
- A gate with a filesystem interface is run from an isolated sandbox root (a copy of the
  script plus fixtures), because it derives `REPO_ROOT` from its own location. A gate whose
  interface is `gh` runs against a stub `gh` first on `PATH`, driven by environment switches,
  so no suite needs the network or a token. A gate whose interface is git runs against a real
  throwaway repository rather than a mocked git.
- Suites that run as a pre-commit hook scrub `GIT_DIR`, `GIT_INDEX_FILE` and `GIT_WORK_TREE`:
  the hook points them at the host repository, and a sandbox `git commit` would otherwise
  rewrite the branch being committed (measured on a scaffold started by that hook, #629).
- Vacuous loops fail: a gate or suite that matched zero items must not pass.
- Cases pinned by specific incidents: `check_pr_file_count` charges a mid-merge index only
  for the branch's own files, including every `MERGE_HEAD` of an octopus merge (186 reported
  versus 69 real) and still fails 91 own files (#560); `check_precommit_ci_parity` must not
  count a workflow that mentions a script only in a comment, and validates its exemption file
  even when no mismatch needs it; `check_docs_boundary` has symlink-loop and unreadable
  directory cases that used to report a clean pass for having checked nothing, and asserts it
  never descends into `templates/` (#576); `check_pr_template` runs against the real
  template, so an edit the gate cannot follow fails there (#672 and #706 are its parser
  cases); `check_specs_structure` runs the project-layout copy with no `--root` from an
  unrelated cwd (#696); `test_spec_answers.sh` pins that `api-service-native-db` borrows the
  DDD key map only while both scaffolds ask the same prompts in the same order (#668);
  `promote_offline_to_online` keeps its fake `gh` ahead of the real one so a regression
  can never reach `gh repo create` with real credentials, and requires the GitGuardian key to
  exist before the push that triggers the secret scan.

## Best Practices

- **Keep branches focused** - one feature/bugfix per branch
- **Make small, frequent commits** - easier to review
- **Write descriptive commit messages** - explain why, not just what
- **Update documentation** - when adding new features
- **Follow existing patterns** - maintain consistency
- **Communicate early** - if you're stuck or need clarification
- **Prompt through the `bin/lib/common.sh` helpers, never a bare `read`** - `prompt_yes_no <var> "$(prompt_main "...")" [y|n]` for y/n questions, `prompt_read <var> "..."` for choices and text. A piped stdin is not an answer: with no terminal both leave the variable at its default, so a stray line on a pipe cannot enable an opt-in. Pick the non-interactive default per prompt (`n` for an opt-in, `y` only when "yes" is the safe unattended answer). When a prompt falls back to its default because stdin is not a terminal, the helper prints one line to stderr naming the prompt and the default (stdout and the exit status are unchanged). A harness that feeds answers on purpose exports `BLUEPRINTX_STDIN_ANSWERS=1`; `bin/lib/spec.sh` (named-key answers, `--spec`) is the supported non-interactive path and sets up that feed, so prefer it over hand-built pipes. `bin/blueprintx.sh` menus are exempt: they have no safe default. `tests/test_prompt_tty_guard.sh` fails on an unguarded `read` in `bin/scaffold/` or `bin/lib/scaffold_*.sh`.

We appreciate your contributions and look forward to collaborating with you!

## Repository scripts under `bin/`

The scripts under `bin/` carry no comments, so the reasoning lives here. Per-script rules,
grouped by what they guard.

### Entry point and shared libraries

- **Version.** `bin/blueprintx.sh` prefers `git describe` from a checkout and falls back to
  the stamped `BLUEPRINTX_VERSION` literal for packaged installs and source archives with no
  `.git`. The literal stays `0.0.0`; the release tag is the single source of truth, and
  `bin/ci/check_version_sync.sh` rejects a hand-bump of it or of `pyproject.toml`.
- **Banner.** Column 72 is the BLUEPRINT/X glyph boundary on every one of the six logo rows
  (#256, verified against `assets/logo.png`): it falls inside the T glyph or a blank inset
  column and the X never starts before column 73, so one split index works for all rows.
- **Two identities in a project name (#113).** A PyPI distribution name may contain hyphens;
  an import package may not (`from my-lib.thing import x` is a parse-time SyntaxError). The
  derivation rescues a hyphen; nothing rescues a leading digit, a dot or a space, so the
  prompt refuses those. The defect hid because the top-level `__init__` compiles either way
  and `importlib.import_module("my-lib")` succeeds on the string form; only a submodule
  import written as source breaks. `bin/ci/check_project_name_identities.sh` therefore renders
  the real templates with a hyphenated name and asks Python to compile them (compile, never
  import, since the rendered modules import a package that does not exist here). The CI
  harness scaffolds with a hyphenated name for the same reason: the previous underscored
  default let the tier shipped an unimportable `src/my-lib/` with the job green.
- **Documentation locale** is the locale of the generated project's published pages only.
  It says nothing about this repository's prose (en-US) or about code: comments and
  docstrings stay English in every locale, enforced in the generated project by
  `bin/check_comment_language.py`.
- **`--spec`** (#481) answers prompts by name instead of stdin position. Resolve the answers
  before the scaffold starts, into a file rather than `$(...)`, which strips trailing empty
  (accept-default) lines; no pipe also means no SIGPIPE status when the scaffold finishes
  before reading every line. Validate in the main shell before piping: a bad y/n must stop
  the run, never become a quiet `n`, and a skeleton with no prompt map is refused up front
  because it would otherwise hang an unattended run on interactive prompts.
  `bin/lib/spec.sh` is the one seam that maps a stable key to the stdin position its prompt
  holds today, so a new prompt needs one new line there. Keys for publishing or registry
  verification must delegate to the `publishprobe` tool, never reimplement credentials.
  `spec_get` tolerates CRLF, a missing file or key (the default applies), and keeps
  `|| true` so a `pipefail` caller does not read an absent key as failure; the emitters wrap
  `spec_get` in `echo` because it prints without a trailing newline and the next answer would
  glue onto it. The review-bot answer is the raw y/n of a `[Y/n]` prompt, not a polarity flip.
- **Colours (`bin/lib/common.sh`, #253, #256).** The six status colours are each bound to one
  `print_status` level, so three more codes exist rather than reusing one with a second
  meaning: `PROMPT_PRIMARY` (bold blue), `PROMPT_SUB` (bold magenta, indented with a `└`) and
  `CANCEL` (the same code as `PROMPT_SUB`, secondary but intentional, never an error). They
  stay out of `templates/common` and `templates/python-common/bin/lib/common.sh`, which are
  copied into every generated project, because "which question is a sub-question" is a
  concept of this menu. The brand tokens (teal 256-colour 73, pink 169, measured from the
  logo) fall back to CYAN and MAGENTA without 256-colour support, and `NO_COLOR` disables all
  three including `BRAND_NC`. An unknown `print_status` level now names itself on stderr: 35
  calls spelled `warn` rendered as unmarked chatter.
- **`sed_inplace` (#459, #502).** GNU `sed -i` takes no argument and BSD requires one, so a
  bare `sed -i` aborts a scaffold on macOS. `-i.bak` satisfies both and the backup is removed.
  It cannot run under `xargs` (a function is not a binary): use a `while read` loop. Backups
  are named per invocation and only for arguments that already name files, so a committed
  `.bak` sibling can never be deleted. It returns sed's own status, not the cleanup's.
  `bin/ci/check_sed_portability.sh` rejects a bare `-i`, including `-i''` and `-i""`, which
  quote removal turns into a bare `-i`; `-i.bak` matches neither branch and comment lines
  are skipped.
- **Env-wise config.** A project's config ships as one `inputs.yaml` or as env-suffixed pairs
  that `ENV` selects through `env_config.resolve_config_path`. The two helpers offer that as a
  scaffold-time choice for every Python service tier; an unknown `ENV` then fails loud, and
  `INCLUDE_ENV_WISE` unset is false.
- **`strip_bump_version`, `add_poe_include`.** A bump task is meaningless once versioning is
  tag-driven, so it is removed on the online path only (offline keeps `cz bump`). One TOML
  table replaced six regexes across the Makefile and `tasks.sh`. Poe warns on every run about
  an included file that does not exist, so the include list names only fragments actually
  copied, idempotently, extending one `[tool.poe]` table.
- **Cache purge.** `cp -r` has no exclusion mechanism, so a `__pycache__` or tool cache in
  `templates/` is copied into the new project, where the generated `.gitignore` hides it.
  CI checks out fresh and never sees one, so it shipped silently from maintainers' machines.
  One purge after the copy phase replaces an exclusion at about 30 call sites.
- **Branch-protection provisioner for non-Python skeletons (#564).** Python tiers get
  `enable_repo_rules.sh` with `templates/python-common/bin/`; TypeScript and Bash had none,
  so no required check at all. Its proper home is `templates/common/bin/`, but
  `verify_branch_protection.yml` hardcodes the Python path, so moving it needs that workflow
  too. The per-tier check list travels as data, and `lib/common.sh` is copied alongside as the
  script's one dependency.
- **`scaffold_git_remote.sh` is separate from `scaffold_python_templates.sh`.** They were one
  file until `bin/ci/check_test_copy_lists.py` went wrong: it treats a scaffold plus the libs
  it sources as the reachable set, and lib-minimal sources the git half without calling the
  Python copy functions, so the union claimed four shared tests reached lib-minimal. Over-
  reporting reachability is the dangerous direction for that gate. A scaffold now sources
  only the halves it uses. The git half replaced six near-identical copies; they differed on
  an optional `--homepage` (`SCAFFOLD_REPO_HOMEPAGE`) and on what runs after the prompt,
  which stays in each caller's wrapper because a flag meaning "which tier am I" is how a
  shared function rots.
- **Remote verification (#212).** Scaffolding into an existing clone used to treat "origin
  exists" as nothing to do, so `gh repo create --push`, the push and branch protection wrote
  to whatever that remote was. Now every URL, fetch and push (`--all`), must reduce to this
  repository's `owner/repo`. The host is matched as a host, not a substring: the first
  version cut at the last `github.com` and accepted `https://evil.example/github.com/o/r`
  (review on #215). `github.com.evil.com/...` also misses. ssh, scp-style and https spellings
  of one repository compare equal; a non-GitHub remote never equals a slug. A return value is
  not enough, because each tier later selects online mode by `rev-parse @{u}`, which is true
  for a clone pointing elsewhere, so the verified result is also published in a variable the
  caller's `main` reads.
- **Exit status of the repo-create step.** The earlier version set `push_done=1` inside a
  `( cd ... )` subshell, so the assignment never reached the parent and the follow-up push
  always ran, in six scaffolds. ShellCheck had reported it as SC2030/SC2031 at `info`, below
  the `warning` floor (see `check_shell.sh`). Testing the subshell's status keeps the `cd`
  contained.
- **Reviewer roster opt-out (#374).** With no reviewer, a generated project's "Review threads
  answered" check can never pass. Omitting `.review-bots.yaml` (never shipping it empty,
  #262) makes the gate self-skip. The TS scaffolds copy `.github` wholesale, so they remove it
  afterwards; lib-minimal gates it in its own function. `docs/faq.md` has the full answer.
  `bin/ci/check_review_bot_roster_optout.sh` copies the real TypeScript `.github` tree (a hand-
  made roster made the "present" case pass even if the template stopped shipping it) and
  extracts lib-minimal's function body to evaluate it alone, since scaffolds run `main` on
  source.
- **Secrets propagated by the scaffold.** Actions secrets are per repository and `gh repo
  create` copies none, so a scaffolded project would have `coderabbit_trigger` without its
  PAT and fail on the first PR. The scaffold sets it, at the one moment the authority and the
  information coexist, from the environment (the shell gets it from a git-ignored
  `~/.claude/.env`); no BlueprintX file ever holds a credential, because a second copy is the
  one nobody rotates. An absent variable warns and does not fail: scaffolding must not abort
  over an optional integration. Pass the PAT with `--body`; a redirect keeps a trailing
  newline that 401s like an expired token. The GitGuardian key is piped on stdin, never
  `--body` (process arguments are readable by any same-host process, CWE-200) and never a
  redirect (the newline hazard); `printf '%s'` avoids both. That variable also *is* the
  opt-in signal for `secret_scan.yaml`, so a failed propagation unsets it at that single
  boundary: otherwise the workflow ships to a repo with no secret and `ggshield` exits 3.
- **Kanban board and labels (#592).** The board mirrors this repository's: Status Backlog,
  Ready, In progress, In review, Done, plus Priority, Size, Estimate, Start date, Target date
  and Points. Views and built-in workflows have no public API, so they are reported, never
  pretended. Only the Status field needs GraphQL (`gh project field-create` cannot edit a
  built-in field). Labels are `name|colour|description` and `--force` makes them re-runnable.
  A token without the `project` scope fails 403, and the message says how to fix it, on
  stderr because callers run inside `$(...)`. Visibility defaults to the repo's own. A board
  is matched on its exact title; several matches mean never guess (return 2). EOF or no
  readable stdin is no: never create a project unasked. Everything is non-fatal.
- **`patch_package_json` (#397).** The project path travels through argv and is never
  interpolated into the Python source: four copies wrote `open('$project_path/package.json')`
  inside a double-quoted `python3 -c`, so an apostrophe in a directory name (`Joao's app/`)
  ended the literal and a newline could inject statements (#396).
- **`scaffold_python_templates.sh`.** `copy_common_templates` was 95 lines duplicated in four
  scaffolds that differed by one token, the tier directory, so 285 lines varied one word. It
  is split into four by destination concern (project identity, tooling config, shared tests,
  executables), not merged into one 95-line function the 60-line gate rejects. Contract with
  `check_test_copy_lists.py`: it follows the `source` line into this file, so moving test
  `cp` lines again moves the gate with them. A declined opt-in's dependency line is pruned
  from the rendered `pyproject.toml` (#274) instead of silencing deptry's DEP002. The
  reviewer roster is data; the tests, leaf `CLAUDE.md` docs, `tests/` leaf doc (one source
  for six tiers, #124, #152), VS Code settings, incident page (#240) and the `.specs/` gate
  copy are single-sourced from python-common so the copies cannot drift. Leaf docs are the
  asset class the copy lists kept forgetting (#325): nothing imports a doc, so a generated
  project is green precisely because it is absent. `check_review_threads.py` lives in
  `templates/common/bin/` (#175) and is copied explicitly to the same destination.

Further facts carried by the removed comments:

- **Rendered assertions.** `scaffold_lint_test.sh` asserts the CODEOWNERS render at the source,
  because the offline run drops `.github/` and cannot see a CODEOWNERS that kept its literal
  `${GITHUB_USERNAME}` (#715).
- **Single-sourced shared files in `scaffold_python_templates.sh`.** The principles file
  (SRP and actor cohesion, Clean Code function principles, #540) is language-agnostic, so it
  lives in `templates/common`. The feature-spec skeleton (#446) gives feature specs a place
  from the first commit and ships no templated principles. Every skeleton's root `CLAUDE.md`
  points at `.claude/CLAUDE.md` for the shared conventions (#549), so the single source is
  copied to keep that pointer from dangling. The gate and example tests were split from
  `scaffold_copy_shared_tests` (#127) to stay under the 60-line ceiling; the pip-fallback
  selector tests cover the PEP 621 layouts no tier ships, the only place the selector could be
  wrong unnoticed (#211).
- **`spec.sh` ownership note.** It is the translator because the scaffold scripts still read
  positional stdin and were owned by other open PRs (#503, #509) when it was written.
- **Reviewer roster.** The copy of `.review-bots.yaml` is also read by
  `scaffold_copy_tooling_configs` (#540).
- **`check_test_copy_lists.py`.** lib-minimal ships neither `ms_office/` nor `email/`
  (service-tier concerns, #118 and #121), so their tests have no module to cover.
- **`check_makefile_pairing.sh`.** `poe_tasks.toml` replaced the Makefile and `tasks.sh` in
  generated projects (#236).
- **`check_docs_boundary.sh`.** It follows the en-US precedent (#194): the rule is this
  repository's, and a generated project may legitimately differ.
- **`scaffold_set_gitguardian_secret`.** Same reasoning as the PAT function, applied to the
  key from #287 instead of the PAT from #155.

Further details restored after review of #805:

- **`check_actions.sh`.** The shell lint of `run:` blocks uses the same rules as the rest of
  this repository, so a block cannot pass one gate and fail the other.
- **`promote_offline_to_online.sh`.** The online state is carried by `HAS_ORIGIN` and
  `HAS_GITHUB_ASSETS`, both set by one detection step and both consumed by the witnesses in
  `main()`.
- **`check_test_copy_lists.py`.**
  - A copy must be proven, not mentioned. An earlier version matched a test filename anywhere,
    including inside the gate's own exclusion prose quoted into a script, which was a false
    pass in the one direction that matters.
  - Leaf docs are keyed by path relative to python-common, because every one is named
    `CLAUDE.md`.
  - The loop form's names may come from a `local -a utils=(...)` array, which exists so the
    step prints a count instead of an enumeration that goes stale; reading only the loop
    header would call every shared test undelivered the moment a scaffold switched form, a
    false failure in a gate valued for catching false passes.
  - A name must look like a util, so a shell token (`"${utils[@]}"`, a `\` continuation) is
    not mistaken for a module. The `(?!#)` comment guard is needed on both patterns: adding it
    to one leaves the other able to satisfy the gate from a comment.
  - A stale exclusion silently keeps an asset out long after its reason expired and reads as
    intentional forever, so it fails.
  - `verify_venv_imports.py` is excluded for lib-minimal because it is only invoked from
    `bin/lib/pip_fallback.sh`, and lib-minimal copies only `bin/lib/common.sh`: no
    `bootstrap.sh`, `pip_fallback.sh`, `venv.sh` or `run.sh`.
- **`check_precommit_ci_parity.sh`.** Stripping YAML comments before matching can only hide a
  match, so the failure direction stays closed. The workflow read is broad on purpose: a
  multi-line `run: |` scalar is plain text and must not be missed. The pre-commit side matches
  the script wherever it sits in an `entry:` (after `bash` or `python3`, before `--root .`),
  and only local hooks have `entry:`. The classifier is a pure decision about one name; the
  caller keeps the counters. The gate is not part of the `bin/ci/*.sh` family that CI jobs
  share with pre-commit, since it concerns neither templates nor generated-project linting.
- **`scaffold_lint_test.sh`.**
  - A git identity is set because the scaffold's first commit needs one and CI runners have
    none.
  - The project venv from `poetry.toml` suffices: drivers ship as wheels and the unit tests
    import DB drivers lazily.
  - Poe goes through the resolver because `poetry install` puts it in the in-project `.venv`
    but not on `PATH`, which is what the first branch of `poe_exec.sh` exists for.
  - A baseline commit is made after `poetry install`, so the post-lint diff reflects only what
    `poe lint` changed.
  - The seeded cache fixtures are `templates/python-common/src/utils/{__pycache__,.ruff_cache,
    seeded_probe.pyc,seeded_probe.pyo}` and `templates/python-common/optional/typing/
    {__pycache__,.mypy_cache}`, six of the eight, which is why concurrent runs collide.
  - The generated `.gitignore` hides `__pycache__`, so `find` is the only witness (#205).
  - Seeding happens only under a directory the template already has: creating the parent
    would change what the scaffold copies.
- **`scaffold_lint_test_all.sh`.** A worker reads only `templates/` and `bin/`, because
  `scaffold_lint_test.sh` resolves its root from `$0`, reads `skeleton.meta` and executes the
  scaffold it names. The worker is a self-invoking mode because `xargs -P` can only fan out
  over a command and an exported shell function is fragile. The sequential loop it replaced
  took about 10 minutes, one tier at a time. Nothing in a worker needs credentials; it installs
  from the public index. `--jobs 2` caps concurrency, and `--jobs 1` is the sequential
  debugging escape hatch.
- **`spec.sh`.**
  - `spec_skeleton_supported` compares by exact equality, since a substring match accepted two
    supported names joined by a space.
  - The status check in `spec_stdin_for_skeleton` is defence in depth: a failure inside a
    pipeline emits no answers instead of stopping it, so `scaffold_from_spec` also reads that
    status from `PIPESTATUS`.
  - The publish and registry keys (`publish_pypi`, `publish_test_pypi`, `consume_private`)
    only answer the scaffold's existing yes/no gate.
  - The problem it solves: an answer stream like `printf 'n\n%.0s' {1..12}` is positional, so
    inserting a prompt anywhere shifts every later answer onto the wrong question; a name does
    not move when a prompt is inserted.
  - `spec_get` prints with `printf '%s'` and no trailing newline so that it composes under
    command substitution.

Lib facts without an issue number, restored after a pass over the removed lib comments:

- **`bin/lib/common.sh` contract.** It is sourced, never executed (it refuses direct
  execution), idempotent through the `_BX_COMMON_LOADED` re-sourcing guard, and shares one
  `print_status` and one colour set across `bin/*.sh` and `bin/scaffold/*.sh`. If a script sets
  `LOG_FILE` before sourcing, `print_status` also appends a timestamped line there; unset, it
  is console only. Levels are `success`, `error`, `warning`, `info`, `config`, `debug` and
  `section`; errors go to stderr, everything else to stdout. `print_section` is a thin
  wrapper over the `section` level for call-site readability, and `exit_error <message>
  [code]` routes through the `error` level (stderr and log) before exiting with the code
  (default 1). Variables whose only reader is another file carry a `shellcheck disable=SC2034`
  with the reason, because ShellCheck cannot follow a standalone lint into `bin/blueprintx.sh`.
- **`resolve_default_branch [name]`.** Order: explicit argument, `$DEFAULT_BRANCH`, the remote's
  `origin/HEAD`, a local `main`, else `master`. It is shared by the `new_branch` and
  `git_merge_to_main` targets so both agree on the integration branch.
- **`sed_inplace` migration.** Replace `sed -i <script...> <file>` with `sed_inplace` and keep
  the rest. For an `... | xargs -r sed -i` site, use the `while read -r file` loop shown in
  `conditional_copy_webhooks_yaml` in `bin/scaffold/python_mvc_service.sh`.
- **`add_poe_include`.** Before the poe migration, removing the bump task edited both the
  Makefile and `tasks.sh` in three places each (six regexes); one TOML table replaced them.
  The Makefile's `-include make/*.mk` made a missing file silent, whereas poe's `include`
  prints `Warning: Poe could not include file from invalid path ...` on every invocation
  (measured), which is how a team learns to read past warnings.
- **Cache purge.** Interpreter and tool caches (`__pycache__`, `.pytest_cache`, `.ruff_cache`,
  `.mypy_cache`) are stripped once after the copy phase, needing no `rsync`.
- **`scaffold_python_templates.sh` placement.** `poe_tasks.toml` replaces the Makefile and
  `tasks.sh` pair; the four service tiers' copies were byte-identical (md5 09515a32) before
  being single-sourced, and lib-minimal keeps its own because its task set differs. A seeded
  `CHANGELOG.md` lets the docs Changelog page (`--8<--` include) build before the first
  release; `cz changelog` regenerates it from tags. Shared tests ship from python-common
  because each tier's `cp -r tests/.` does not reach `python-common/tests/`: the reference
  integration test for the shared `bin/` shell seams (`poetry_exec.sh`, `precommit.sh`, see
  `bin/CLAUDE.md` "Testing shell scripts"), the network-block guard (its `conftest` makes a
  real network call impossible in any test) and the introspective-convention example that
  enforces a family convention through `__all__`. The contract-drift test ships to all five
  tiers and self-skips at module level in lib-minimal, which has no contract registry. The
  incident-record page (#240) is copied here rather than in each tier's mkdocs step because
  `docs/` already exists by then and the file was not touched by any in-flight PR. The tier's
  `src/config/CLAUDE.md` is copied by each tier's `copy_global_config`, next to the payload it
  documents; the copy-list gate accepts either home. VS Code settings are shared from
  python-common and the tasks are per tier because the commands differ.
- **`scaffold_git_remote.sh`.** It reads `GITHUB_USERNAME`, `DEFAULT_GITHUB_USERNAME`,
  `PROJECT_NAME` and `PROJECT_DESCRIPTION` from the caller. `SCAFFOLD_REPO_HOMEPAGE` and the
  roster flag use the `:` default-assignment idiom so ShellCheck sees the value as read
  instead of flagging SC2034 for a consumer in another file. The roster default is `true`:
  every project scaffolded before the flag existed shipped it.

### Gates in `bin/ci/` and `bin/`

- **`check_makefile_pairing.sh` (#241).** Every user-facing Makefile target needs a `case`
  branch in `tasks.sh` and a line in `bin/help.sh`. Root-repo-only: those files exist only at
  this root, so the gate lives at `bin/`, outside `bin/ci/` (which #271 was reworking), and is
  not part of the family CI and pre-commit share. A target preceded by a `# pairing:internal`
  line is exempt; the marker must be the whole comment token, since a substring test also
  accepted `pairing:internalized`. Every name before the colon counts (`build test:` declares
  two), `dev-clean` and `dev_clean` are equivalent in both companions, and normalising in only
  one made a correct pairing fail.
- **`check_precommit_ci_parity.sh` (#384).** It verifies pre-commit and CI run the same
  checks. The join key is the invoked script, never a hook id or job name, because the two
  sides express a check differently (51 hooks versus one CI job of 31 steps on the scaffold
  side). It scans every workflow, not only `scaffold_checks.yml`: `check_secrets.sh` looks
  pre-commit-only from there and runs in CI from `secret_scan.yml`. Candidates are scripts in
  local hooks, plus `bin/ci/`, plus `check_makefile_pairing.sh`; repo automation such as
  `pr_reconcile.sh` was never a candidate. The check is for invocation, not presence: YAML
  comments are stripped and the name must sit at a command position (a comment naming a
  script used to pass a script CI never runs). Match with a here-string, never
  `sed | grep -q`: `grep -q` closes the pipe, `sed` dies of SIGPIPE and `pipefail` reports
  141, so a script that is invoked read as absent (17 false mismatches over 24 scripts, only
  on inputs big enough that `sed` was still writing). Exemptions are data in
  `bin/precommit_ci_parity_exemptions.txt`, one `script|side|reason` per line, side being
  `precommit_only` or `ci_only`; a reason-less entry is rejected, and the whole file is
  validated up front rather than only when a mismatch consults it. `printf '%s\n'
  "${arr[@]}"` with an empty array still prints one blank line and would manufacture a phantom
  candidate, so it is guarded.
- **`check_actions.sh`.** actionlint over this repo's workflows and those under `templates/`.
  yamllint validates YAML, actionlint validates a workflow, and a workflow GitHub rejects
  produces no red check. The templates are in scope because they never execute here; the
  first run found 8 defects, including `actions/cache@v3` in three tiers and a `workflow_call`
  output that could only resolve to the empty string. One false positive is tolerated by
  rule: a template's local `uses: ./.github/workflows/...` resolves against the generated
  project. Group `-name '*.yaml' -o -name '*.yml'` before `-type f`. Templates have two
  shapes: `.github/workflows/` copied wholesale, and conditionally copied workflows under
  `optional/deploy/`, which a path filter anchored on `.github/workflows` would miss. Every
  job with a runner must set `timeout-minutes` (default 6 hours; measured twice in two days on
  an `apt-get` step across 22 workflows with no bound, #192); jobs that only `uses:` a
  reusable workflow are skipped. Every remote action is pinned to a 40-hex SHA with a trailing
  `# vX.Y.Z` (#369): a tag is a movable pointer. Discovery must match something, and the
  count is printed. The pin and timeout checks need no tool, so they run before the
  actionlint resolve and never inherit its graceful skip, which is a placebo in CI
  (`LINT_ACTIONS_REQUIRED=1`). A comment in a workflow may not start with the tool's name, or
  it parses as a lint directive. The filter that limits the pin check to templates stays only
  until this repository's own workflows are pinned (follow-up from #369); then drop it and
  pass the full list.
- **`check_codespell_sync.sh`.** The two `ignore-words-list` values must match. They drifted in
  both directions (30 words missing from the template, 25 the other way) and the template was
  the stale side, so each generated project re-learned words one rejected commit at a time.
  Compare verbatim and sorted, not case-folded: codespell splits the list in two, so a
  lowercase entry filters its typo dictionary while a cased one matches only that
  capitalisation, and folding before comparing would call two differently behaving configs in
  sync. Entries with an uppercase letter are rejected: the found word is lowercased before
  lookup, so a cased entry is never more useful than its lowercase form.
- **`check_docs_boundary.sh` (#536, #576, #632).** `docs/` is solely for published
  documentation (owner rule, 2026-09-18). Anything else is redirected, not merely rejected,
  so every rule names a destination: `docs/backlog/` to `.specs/` or `CONTRIBUTING.md`; a
  basename containing "lesson" to the operator's lessons stores (a hardened rule goes to
  `CONTRIBUTING.md`); `design.md` and `plan.md` to `.specs/features/<name>/` (#447);
  `security.md` and `threat*.md` to the root `SECURITY.md`, which GitHub reads only from the
  root, `.github/` or `docs/` root; any `.superpowers*` segment to that tool. The list is open
  and grows with each new kind of working material. A matching directory is reported once and
  not descended into. It walks only this repository's `docs/`, never `templates/*/docs/`,
  deliberately and with no `--root` flag: `docs/backlog/` is a violation here and a shipped
  product surface in the five tiers (gated by `check_backlog_ledger.py`), and a knob nothing
  turns invites widening the scope unasked. `dotglob` and `nullglob` keep hidden entries
  visible and an empty directory from yielding the literal glob. An unreadable directory must
  fail (a `docs/secret/` at mode 000 holding a real violation once printed "boundary is
  clean"). A symlink is classified then treated as a leaf (a link to an ancestor re-entered
  the tree through a longer path: "163 entries checked" on a 3-file fixture, stopped only by
  `ELOOP`). A readable `docs/` with zero entries fails. It judges what git would publish,
  only when the top level is this repository (an enclosing repo's `.gitignore` must not
  decide), with `GIT_DIR`/`GIT_WORK_TREE` and the global excludes file kept out, and
  `GIT_INDEX_FILE` kept so a pre-commit run judges the index.
- **`check_gate_staleness.sh` (#368).** A report, not a fix: `gh pr update-branch` moves the
  head and can flip a clean review to SUPERSEDED (measured on #444). It pairs "behind base"
  with "a gate file changed since the merge-base". It fetches `refs/pull/<n>/head`, not
  `headRefName`, which does not exist on `origin` for a fork PR and could silently resolve an
  unrelated branch. Advisory, never failing: a red required check would pressure a mass
  update-branch, a review-quota burst. The gate-relevant path list is kept in sync by hand
  with the gate table in `CLAUDE.md`.
- **`check_git_remote_guard.sh` (#212).** Negative control for the remote check: the dangerous
  direction is a false pass on a foreign remote, so the case that matters asserts a mismatch
  fails. Status alone is not the assertion: a pass must leave `origin` on our slug and a fail
  must leave it untouched. It covers a remote that fetches from us but pushes elsewhere, a
  missing secret not killing a scaffold run under `set -e`, one repository spelled four ways
  reducing to one slug, a non-GitHub remote never equalling a slug, and host confusion.
- **`check_issue_scope.py`.** An empty fence, or one holding only comments, is undeclared and
  never "declared as nothing": an empty set would put every file outside the surface and fail
  every PR, and the issue template ships exactly that shape.
- **`check_markdown.sh` (#383).** `pymarkdownlnt` over every tracked `.md`, with a measured
  rule set in `.pymarkdown.json`: MD018/019/020/021/023, MD047, MD009. MD013 and MD040 are off
  because both fired on the bulk of the prose, the "number nobody pays" shape of
  `check_complexity.sh`'s history. The measured counts and the tool comparison are in the #383
  PR body. It is deliberately not shipped into generated projects. Resolve, do not install: a
  missing tool is a graceful skip locally and `MARKDOWNLINT_REQUIRED=1` hard-fails in CI.
- **`check_pr_file_count.py` (#551, #560).** CodeRabbit refuses to review above 100 files
  ("Review skipped: N files exceed the limit of 100"), so the ceiling sits 10 below it: a PR
  that trips the vendor cap is already too late. Calibrated over 100 PRs: 1 violation (#424,
  241 files) against a legitimate maximum of 59 (#532); #424's seam was real, and none has
  surfaced since, so there is no escape hatch. Mid-merge, the index holds the incoming side
  while `HEAD` is the pre-merge tip, so the base comes from `git merge-base` over the merge
  commit about to be created (186 reported versus 69 real). The `git` call is a constant
  argv with no shell; S607 is by design, because the hook must use the developer's `PATH`
  `git`. A Windows cp1252 stdout would raise `UnicodeEncodeError` on the status glyphs and
  block every commit from a Windows checkout, so it is guarded. A detached HEAD compares tips;
  unrelated history or a too-shallow clone has nothing to check.
- **`check_pr_template.sh` (#587, #672, #706).** It checks a PR body against the layout the
  template declares: every `##`/`###` heading and `**Label**:` field must appear at line start
  with real content, bar the conditional ones. The contract is walked out of the template, and
  only the mandatory-versus-conditional split is data. Keys are `<kind>:<section>/<name>` so a
  label in the wrong section is not credited. HTML comments and fenced code are dropped, a
  fence judged first. A line is credited to the innermost open scope. A bullet that is only a
  bold label is structure, neither placeholder nor content. Use `if`, not `&&`, where a false
  last statement would exit under `set -e`. A classification naming a label the template no
  longer has fails rather than rotting. **Not Applicable** is required exactly when a testing
  subsection is not filled in. Rationale for humans is in "PR template layout".
- **`check_shell.sh`.** ShellCheck at warning or above, with `-x` following `source` into
  `bin/lib` guided by `# shellcheck source=` directives: a variable whose only consumer is a
  sourced lib otherwise reads as SC2034, which is a question ShellCheck cannot answer one file
  at a time, and following it makes the finding disappear because it stopped being true. A
  second targeted pass includes SC2030 and SC2031 (a variable set in a `( ... )` subshell is
  lost to the parent), rated `info` and so filtered out; that is how the `push_done` bug
  survived. The rest of the `info` tier (SC2059, SC2016, SC1091, about 78 findings) is noise.
- **`check_specs_structure.sh` (#447, #583, #696).** One implementation for this repository
  and every generated project (the file is copied to the project's `bin/`); the root is two
  levels up from `bin/ci/` here and one up from `bin/` in a project, and survives
  `cd bin/ci && bash ...`. The rules: `.specs/CLAUDE.md` exists; the top level allows only
  `CLAUDE.md`, `features/`, `backlog/`, `_lessons/` (free-form); `features/` holds kebab-case
  directories with a letter and never a change type (dotfiles-dev#442), because `[a-z0-9]`
  alone accepts a bare `447`; each holds `design.md`, `plan.md` or `tasks.md` (`pr.md` is
  recognised but never sufficient); every task line is `[ ]`, `[~] <type>/<branch>` or `[x]`,
  outside code fences (a fence closes on the same character, at least as long); `backlog/` is
  flat `<kebab-topic>_YYYYMMDD_HHMMSS.md`. `dotglob` and `nullglob` so a hidden entry is not
  walked past. A missing `--root` fails (it would report "no `.specs/`" and succeed), and no
  `.specs/` at all is not an error.
- **`check_test_copy_lists.py`.** It asserts every shared test, workflow and leaf doc is
  reachable from each scaffold's copy list. Both patterns must prove a copy, not a mention:
  an `cp` whose *source* operand is the shared path (immediately after `cp` and its flags, or
  a reverse copy would count), uncommented (`(?!#)` on both patterns, or the other can satisfy
  the gate from a comment), and the loop form must be the real `copy_shared_utils` body that
  copies `test_${util}.py`, with names read from the header or a `local -a utils=(...)` array.
  Exclusions are claims that a tier cannot use an asset, not shortcuts, and a stale one fails.
  Recorded clean exclusions: lib-minimal has no runtime `.env` (env-config seam), no database
  engine (query loader), no contract registry or drift reporter, no `__all__` packages, no
  import-time bootstrap, no `ms_office/` or `email/` packages, and no pip-fallback bootstrap
  (`verify_venv_imports.py`). Known gaps, recorded rather than hidden: lib-minimal vendors the
  helpers under `_internal/utils/` with rewritten imports, so those modules ship without
  their tests until `rewrite_internal_imports` runs over the test files; `config/schemas`
  tests wait for `pydantic` to be a declared dependency (#267, remove the exclusion with the
  `cp` line); the dead-code gate waits for `vulture` (#332); `check_migration_graph.py`'s test
  has no `cp` line yet (#308); lib-minimal's `test_typing.py` is rendered from
  `templates/lib-minimal/rendered/test_typing.py.tmpl` by `envsubst` (a heredoc until #189),
  a third delivery mechanism the gate does not model. Leaf docs are the third copy-list asset
  class with this defect, the quietest (#325), and `python-common`'s root `CLAUDE.md` is the
  one doc that must never ship. A doc is reachable by its own `cp` or a wholesale directory
  copy only when the destination stays inside the project and keeps the source name (#569).
  Workflows are the second copy list with this defect, and worse: a job no scaffold copies is
  a gate that does not exist in any generated project, and nothing reports a workflow never
  installed. It was found when adding `review_threads.yaml` showed the `cp` list would not
  carry it. Workflow exclusions: a library publishes through its own release-pypi and
  release-test-pypi pair, and contract drift describes an ingested external file, which a
  library registers none of. lib-minimal ships its own `config_CLAUDE.md` and
  `utils_CLAUDE.md` from `templates/lib-minimal/` because its `_internal/` layout differs
  from the service tiers'. `api-service-native-db` excludes the `config/schemas` test for the
  same reason as its siblings: `fastapi` pulls `pydantic` in transitively, which is not the
  claim #267 makes (declare it as a direct dependency), and the module the test imports is not
  shipped by that tier either. Scanning nothing is not a pass, and Windows stdout is guarded
  for the status glyphs.
- **`reevaluate_issue_scope.sh` (#314).** The PR-event job runs when the PR changes, never
  when the issue changes, so a surface edited later leaves a green status describing an older
  declaration. This posts a commit status on each open PR whose `closingIssuesReferences`
  (what GitHub acts on at merge, never a branch-name guess) names the edited issue. Its
  context is deliberately distinct from the PR job's check name: a status and a check run
  sharing a name are ambiguous for branch protection. It fails the job too, since a red
  status on someone else's PR is easy to miss from the issue timeline. See `docs/issue-scope.md`.
- **`validate_meta.sh` (#407, #478).** Every `skeleton.meta` has all four fields non-empty, a
  `scaffold=` path that exists, and the skeleton directory named in the root `CLAUDE.md`:
  machine-decidable, so a gate, while the quality of the mention stays a human call. A missing
  key under `set -euo pipefail` used to kill the gate inside its own `grep` pipeline with exit
  1 and no message, which every should-fail test read as proof the check ran; hence `|| true`.
- **Shell helper scripts.** `check_docs_build.sh` builds MkDocs `--strict`, preferring `poetry
  run` and falling back to `mkdocs` on `PATH`; `check_spelling.sh` runs codespell over `docs/`
  and `templates/` with the root `.codespellrc`; neither inlines flags, so CI and pre-commit
  cannot drift. `smoke_test.sh` computes menu indices dynamically from `skeleton.meta` with
  the same glob order and de-duplication as `blueprintx.sh`, so directory reordering cannot
  break it. `optin_specs/storage.answers` answers the storage opt-in `y` so the harness lints
  the `chassis/db_wschema` files that ship only on that opt-in (#650).
- **`check_orphan_pr_bodies.sh` (#657).** A report-only, local-only scan of PR and issue
  bodies left in `<repo>/.git/*.md` that match nothing on the forge (`.git/` is outside the
  worktree, so no CI job can see them). It never deletes or moves anything. Matching is by
  content through one normaliser on both sides (NFKC, case-folded, all Unicode whitespace
  collapsed, `[x]` read as `[ ]` because ticking a box rewrites the stored body); MATCHED
  means the local body is contained in exactly one forge body, one way only, so a forge body
  that is just the unfilled template cannot match every local body. A body edited on the
  forge since is UNKNOWN, never ORPHAN. It fails closed: anything undecidable (forge
  unreadable, no origin, body under 40 characters, ambiguous or near match) is UNKNOWN.
  Usage `bin/check_orphan_pr_bodies.sh [git-dir]`; `BLUEPRINTX_REPO=owner/name` overrides the
  slug parsed from `origin`. Exit 0 all matched, 1 an orphan, 2 could not decide, and 2 takes
  precedence: one UNKNOWN hides ORPHANs from the code, not from the report. It scans
  `<git-dir>/*.md` only, not `worktrees/*/`. A body mostly built from the PR template can read
  UNKNOWN instead of ORPHAN: a false negative, never a false ORPHAN. REST on purpose, since
  GraphQL is rate-limited more tightly, and a traceback is never ORPHAN.
- **`promote_offline_to_online.sh` (#382).** Turns an offline project into an online one
  without re-scaffolding. It adds the GitHub-only assets, creates and pushes the repo,
  applies best-effort branch protection and removes the offline fallbacks. It is standalone:
  it transcribes the scaffolds' manifests (see `docs/offline-to-online.md`) rather than
  sourcing scripts other PRs hold. It refuses rather than guesses: an unknown tier or one
  whose skeleton is gone, a typo'd or tier-inapplicable `--publish`/`--deploy-target`, a
  directory merely inside another repository (`rev-parse` succeeds there, and `gh repo create
  --source=.` would publish the parent), and a non-`main` branch (`--push` pushes the current
  branch while protection targets `main`). A resume after a failed promotion commit allows
  only the paths the script itself writes; anything else is the user's work. The original
  PyPI or deploy choice is not recorded offline, so the flags decide (default `none`).
  CODEOWNERS is the one file every tier writes, so it decides "online" for
  `react-spa-webpack --deploy-target none`. `secret_scan.yaml` is opt-in on
  `GITGUARDIAN_API_KEY`; the repo is created without `--push` so the key exists before the push
  that triggers the workflows (otherwise the first run is red). The key goes on stdin. The
  restored `no-commit-to-branch` hook is the only one skipped for the promotion commit.
  `git_diffs/` is removed only when it holds just the `.keep` placeholder. Branch protection
  warns rather than aborts. Each reversal is idempotent. The file ends guarded so tests can
  `source` it.
  More promote rules: `shift 2` on a lone flag fails silently under `set -e`, so flags are
  checked first. "Online" is told from "remote added, nothing pushed" by the local
  `refs/remotes/origin/<branch>` ref, which `gh repo create --push` records only on success
  (no network). An already-online project is a clean no-op, while an origin without the
  GitHub assets is ambiguous and refused. `bin/lib/common.sh` is left alone, since it is not
  offline-only. The TypeScript and Bash tiers ship no `SECURITY.md`, `dependabot.yml` or
  `secret_scan.yaml`, so nothing of those comes back. An offline project commits on `main` by
  design, which is why only `no-commit-to-branch` is skipped for the promotion commit.
  Branch protection warns instead of aborting because a fresh repository can lag behind API
  visibility and a solo maintainer's review policy is a judgment call the script does not
  prompt for; the assets are already pushed by then.
- **`scaffold_lint_test.sh`.** The real verification for template work, complementing the
  dry-run `smoke_test.sh`. It scaffolds a project, runs its own lint (which must change
  nothing), unit and integration tests. It seeds interpreter-cache fixtures into `templates/`
  before scaffolding (#205): `cp -r` has no exclusion, CI never has a cache, so the harness
  reproduces the precondition itself. One entry per directory name the assertion rejects (a
  check that cannot fail for the cases it claims is vacuous; #215), plus loose compiled
  artifacts outside cache directories, only under directories the template already has, with
  a floor of 4 for lib-minimal. Answers come from `bin/lib/spec.sh`, so a new prompt fails in
  `spec_stdin_for_skeleton` instead of shifting every answer; `SCAFFOLD_SPEC_FILE` overrides
  it, and an unusable override fails rather than reading as all-default. It asserts the
  offline scaffold ships no GitHub-only asset, runs the project's `.specs/` gate on the
  skeleton (must pass) and on a copy with a stray note (must fail), checks that
  `poetry.lock` is not ignored (an absence an unrelated `*.lock` edit would reintroduce,
  #235) and that `cz` still answers (it prints "No project information in this project." and
  exits 0 without `.cz.toml`, #233). It runs poe through the resolver, never bare, and the
  integration suite is where every `bin/*.sh` seam is executed. `|| [ $? -eq 5 ]` tolerates
  pytest's "no tests collected".
- **`scaffold_lint_test_all.sh` (`make verify_tiers`).** Runs every Python tier in parallel,
  each worker in its own copy of `templates/` and `bin/` (about 9 MB): the tiers are not
  independent, because the harness seeds fixtures and removes them in an EXIT trap and six of
  its eight fixtures sit in the shared `templates/python-common/` tree, so the first tier to
  finish deletes the others' fixtures: an intermittent, misattributed failure. The worker
  disables Poetry's keyring (`PYTHON_KEYRING_BACKEND`): concurrent `poetry install`s race on
  the DBus session bus ("Message recipient disconnected from message bus without replying",
  1 of 5 tiers, passing sequentially); that fix lives here and not in the harness, which also
  runs one job per tier in CI. It uses a status file per worker, since `xargs -P` collapses
  statuses (123) and cannot say which tier; a worker that wrote none died and counts as
  failed. Tiers are discovered from `skeleton.meta` with `language=python`, never a list, and
  zero discovery fails. CI does not need it (`tests.yaml` runs one job per tier). Flags:
  `--jobs N`; `--jobs 1` serialises for debugging.
- **`check_version_sync.sh`.** See "Version" above: both literals stay the `0.0.0` stub.
- **`update_licenses.sh`.** The AGPL-3.0 closes the SaaS loophole (network use counts as
  distribution), so the AGPL preamble states the dual-licensing model: organisations that
  cannot comply must obtain a commercial licence from the copyright holder. SPDX ids map to
  GitHub Licenses API keys in display order.
