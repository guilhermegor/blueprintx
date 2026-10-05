# Poe the Poet migration + PR-1 bundle (#232, #235, #233, #211)

Created 2026-08-23. Tracks the two-PR migration of the Python tiers' command interface
(`Makefile` + `tasks.sh` → bootstrap + `poe`) and the three adjacent issues bundled into PR 1
because they share the same expensive verification (`bin/ci/scaffold_lint_test.sh` across all
five Python tiers) and the same scaffold copy-list surface.

## Shape

| PR | Content |
|---|---|
| **PR #236** (this branch) | #232 step 1 + #235 + #233 + #211 — **and, by the owner's call on 2026-08-23, the swap itself.** The two-PR shape #232 asked for was dropped deliberately; recorded here so the deviation is visible, not inferred. |

⚠️ What the single-PR shape costs, since it was a deliberate trade and not an oversight: the PR
was CLEAN with 35 green checks before the swap was added, and `bin/ci/scaffold_lint_test.sh` is
**itself** one of the files the swap rewrites. A bug in the harness and a bug in the ported
tasks are therefore indistinguishable from the outside. There is no mitigation available that
does not violate the two-interface rule (a thin Makefile shim delegating to poe would BE the
third interface), so the mitigation is care, not structure.

⚠️ The failure to avoid, restated from #232: ending at **three** interfaces instead of two.
PR 2 is only worth merging if it ends at exactly `bootstrap` + `poe`.

## PR 1 — #232 step 1: move multi-line recipe bodies into `bin/`

- [x] `lint` — 14 inline steps duplicated in **both** `Makefile` and `tasks.sh` → `bin/lint.sh`
- [x] `test_cov` — 4 more, also twice → `bin/test_cov.sh`
- [x] Audit what is left. **Result: nothing more to extract.** Measured after the two
      extractions: the largest remaining `Makefile` recipe is `help` at 3 trivial `printf`/`cat`
      lines, and every other one is ≤2. The `tasks.sh` functions that *look* long
      (`check_commit_msg` 11 lines, `bump_version` 8, `changelog` 5) are **comment**, not logic —
      each carries 1–2 executable lines. Extracting them would move the documentation, not the
      duplication, so the house rule is already satisfied.

## PR 1 — #235: assert the generated project tracks its lockfile

- [x] Assert in `bin/ci/scaffold_lint_test.sh` that the generated project's initial commit
      tracks `poetry.lock` (`git ls-files --error-unmatch`), failing loudly and naming the tier
- [x] Negative control: prove the assertion FIRES when `poetry.lock` is untracked. Ran with
      `poetry.lock` appended to the template `.gitignore`: `lib-minimal` exited **1**, naming
      the tier, and the `git check-ignore -v` line in the failure output pointed straight at
      `.gitignore:83:poetry.lock` — the diagnostic paying for itself. Restored from a snapshot
      copy, never `git checkout`, per `tests/CLAUDE.md`.
- [x] Holds on all five Python tiers (the `.gitignore` ships from `python-common/` to each)
- [x] Decide on `uv.lock` — out of scope until a tier uses uv

## PR 1 — #233: `[tool.commitizen]` out of `pyproject.toml`

- [x] Move `[tool.commitizen]` to a standalone `.cz.toml` in all five tiers
- [x] Verify **every** consumer, not just the obvious one: `make bump_version` / `cz bump`,
      `make changelog` / `cz changelog`, the `commitizen` pre-commit hook, the `commit-msg`
      hook, and the docs build (which regenerates `CHANGELOG.md`).
      ⚠️ A commitizen config that stops being found does **not** error — it falls back to
      defaults, so the failure surfaces as a differently formatted changelog, never a red check.
      The verification is worth more than the move.
- [x] Confirm `.cz.toml` reaches every tier through the scaffold copy lists
- [x] Record the "cannot move" table in `templates/python-common/CLAUDE.md`, including the
      `poetry.toml` ≠ `pyproject.toml` distinction, so the question is answered in the repo
- [x] Check BlueprintX's own root `pyproject.toml` (docs-only) for anything extractable

## PR 1 — #211: pip fallback picks the Poetry path for an optional-only PEP 621 project

- [x] Fix the detection in `templates/python-common/bin/lib/pip_fallback.sh`
- [x] Negative control proving the wrong branch was taken before the fix

## Verification (shared — the reason these four travel together)

- [x] `bin/ci/scaffold_lint_test.sh` green on **all five** Python tiers — every one EXIT=0, and
      both new assertions fired in each: `tracks poetry.lock` and
      `commitizen resolves its config (0.0.1)`
- [x] Re-verified on all five tiers AFTER the poe swap (EXIT=0 each), plus a re-run of one tier
      following the final doc pass, since edits landed after that batch started.
- [x] Root `make lint` (mirrors CI) — 21/21 gates
- [x] The harness earned its keep on this very PR: it caught an `E501` in the new test that the
      root `make lint` cannot see, because a tier lints with its OWN pinned ruff

## Decision — install channel, settled 2026-08-23 (REVISED the same day, by measurement)

**Final: poe as a dev dependency; bootstrap runs the shell scripts directly.** No Poetry
plugin is declared.

### How it got here — the first answer was wrong and the harness said so

The owner first chose the **Poetry plugin** (`[tool.poetry.requires-plugins]`), because it is
the only route that reaches the bootstrap tasks: Poetry exists before `.venv` does, so
`poetry poe venv` could have collapsed this to ONE interface. Two things then happened, in
order, and both are worth keeping:

1. **The owner's own question exposed a design hole before any code ran.** *"If the
   never-bare-`poetry` rule exists because Windows/Git Bash may only expose `python -m poetry`,
   what exactly is `poetry poe lint`?"* — it is a bare `poetry` call, which
   `templates/python-common/CLAUDE.md` forbids in any recipe, hook `entry:` or `bin/*.sh`. A
   human may type it; a script may not. That produced `bin/poe_exec.sh`, which survives the
   revision below and is the durable part of this decision.
2. **`[tool.poetry.requires-plugins]` then BROKE `poetry install`.** `poetry install` provisions
   a project-scoped plugin environment keyed by project **NAME**, not path. The CI harness
   scaffolds every tier as `ci-scaffold` into a fresh temp dir, so its SECOND run failed
   against the FIRST run's deleted directory:

   ```
   Installing Poetry plugins only for the current project...
   Path /tmp/tmp.aNc5Fjurfv/ci-scaffold for ci-scaffold does not exist
   ```

   Removing the declaration made the same run pass. This is exactly the "prove it works before
   porting" step #232 demanded — and it failed on Linux, without ever reaching the corporate box.

⚠️ **This still ends at exactly TWO interfaces**, which is #232's hard requirement:

| Layer | How |
|---|---|
| Bootstrap (`.venv` does not exist yet) | `bash bin/venv.sh` — the shell entrypoint |
| Everything else | `poe <task>` |

The bootstrap tasks (`init`, `venv`, `ensure_env`, `precommit`, `update_venv`) still EXIST in
`poe_tasks.toml` so the command list is complete and discoverable; they simply cannot be the
first thing you run. A hand-installed plugin (`poetry self add 'poethepoet[poetry_plugin]'`)
keeps working — `poe_exec.sh` still resolves it — it is just not declared.

### `bin/poe_exec.sh` — the resolver, four routes in order

All measured against poe 0.48.0 / poetry 2.4.1 on 2026-08-23:

| Order | Route | Why it is where it is |
|---|---|---|
| 1 | `.venv/bin/poe` | **Load-bearing, not an optimisation.** `poetry install` puts poe here but NOT on PATH, and `$PYTHON` is the SYSTEM interpreter — so routes 2 and 3 are both blind to it. That is the CI case exactly. |
| 2 | `poe` on PATH | a pipx install, or an activated venv |
| 3 | `$PYTHON -m poethepoet` | installed as a library, console script not on PATH (the Windows/Git Bash shape) |
| 4 | `poetry poe` | only if someone installed the plugin themselves |

⚠️ The module is `poethepoet`, **not** `poe` — `python -m poe` fails with "No module named poe".

The resolver is **not** the third interface #232 forbids. It is plumbing of exactly the kind
`bin/poetry_exec.sh` already is: a human types `poe lint`, scripts call the resolver.

### Other facts established the same day, each of which could have changed the shape

- `poe_tasks.toml` is auto-discovered standalone — with **and** without a `pyproject.toml`.
- The Poetry plugin reads that same standalone file, so #232's "tasks in a dedicated
  `poe_tasks.toml`" never conflicted with the plugin path.
- **Tasks run inside the project venv automatically.** Poe detects `./.venv` and runs each task
  under it — verified with a task printing `sys.executable` while a different interpreter sat
  first on PATH. So every task is a BARE command (`pytest tests/unit/`), never `poetry run …`,
  and `poetry_exec.sh` survives only for Poetry MANAGEMENT commands.
- **Extra CLI tokens pass through** to a task with no declared `args`
  (`poe unit_tests -k kw` → `pytest tests/unit/ -k kw`), which is why `test_feat` was DELETED
  rather than ported. Corollary: declaring `args` turns passthrough OFF.
- ⚠️ **Poe's `include` is NOT make's silent `-include`.** A missing include does not fail, but
  it WARNS on every invocation. So the conditional fragments are wired by the scaffold
  (`add_poe_include`), naming only what it copied — an online non-lib project gets no `include`
  line at all, and therefore no warning. A tolerated warning is a warning nobody reads.

## The swap (in this PR)

- [ ] **DEFERRED — owner's call, 2026-08-23.** Prove `poe` installs and runs on Windows/Git
      Bash behind the TLS proxy. #232 wanted this **before** porting; the owner has explicitly
      chosen not to run it now, so the port proceeds and this becomes a post-merge to-do on the
      real machine. ⚠️ What that trades away, stated plainly so nobody rediscovers it as a
      surprise: if the install turns out to be blocked there, #232's own instruction is to
      *reopen the comparison* rather than push through — and by then the Makefile/tasks.sh pair
      is already gone. Mitigation while it is unproven: **keep the shell bootstrap
      entrypoint**, so a box that cannot get `poe` can still reach `venv`/`init` and is merely
      inconvenienced rather than bricked.
      Verify on the Windows box: (a) `pipx install poethepoet` OR
      `poetry self add 'poethepoet[poetry_plugin]'` completes through the Nexus;
      (b) `poe lint` and `poe unit_tests` run from Git Bash; (c) `shell`-type tasks behave
      (poe runs them under `sh`, which Git Bash provides but PowerShell does not).
- [ ] Decide between the three install channels, now that #232 records all three (2026-08-23):
      pipx-global, dev-dependency, and the **Poetry plugin**
      (`[tool.poetry.requires-plugins]`). The plugin is the only one that can collapse this to
      ONE interface — it lives with Poetry, which exists before the project venv — and its
      channel is already proven here (`requirements.txt` pins two Poetry plugins today). Its
      cost: upstream recommends the plain CLI, `--no-plugins` anywhere silently disables it,
      and it assumes Poetry exists, which `bin/lib/pip_fallback.sh` exists to not assume.
      Suggested: **both** — plugin as the normal path, pipx `poe` as the documented fallback.
- [ ] If the plugin is adopted, add `[tool.poetry.requires-plugins]` to the "cannot move" table
      in `templates/python-common/CLAUDE.md` (it is installer input Poetry reads from the
      manifest), so it does not contradict the #233 answer written in this same PR
- [x] `poe_tasks.toml` in `templates/python-common/`, all 35 targets ported (34 tasks —
      `test_feat` deleted, since poe passes extra CLI tokens through to `unit_tests`)
- [x] Bootstrap decided and written down: the shell entrypoint (`bash bin/venv.sh`). See the
      decision section above — the Poetry plugin was tried first and removed by measurement.
- [x] Every caller updated. Measured smaller than feared: `.pre-commit-config.yaml` and the
      template CI workflows referenced `make` only in COMMENTS, never in a command. The real
      work was `bin/ci/scaffold_lint_test.sh` (the verifier itself), `bin/help.txt` (deleted —
      poe generates the listing), the six `.vscode/tasks.json` files, and ~60 doc/comment
      references across `templates/` and `docs/`.
- [x] `.vscode/tasks.json` single-sourced. The four service tiers carried BYTE-IDENTICAL copies
      (md5 `09515a32`) — four copies of one file, the drift `check_codespell_sync.sh` exists to
      police. Now one file in `python-common/`; lib-minimal keeps its own (genuinely different).
- [x] `strip_bump_version` rewritten: six regexes over `Makefile` + `tasks.sh` became one TOML
      table removal, and it now FAILS LOUD if `bump_version` survives the strip.
- [x] `add_poe_include` added for the conditional fragments (see the include warning above).
- [x] The `tasks.sh` integration test became the `poe_exec.sh` one — the DEFECT outlived the
      file (an entry point calling `print_status` without sourcing the lib that defines it).
- [ ] Delete `Makefile` + `tasks.sh` from the Python tiers, or state plainly why one stays

## Found while migrating — `poe lint` does not run every gate (NOT a regression)

Raised by the owner on 2026-08-23 ("shouldn't all the lint gates run under `poe lint`?"). The
three standalone lint tasks they asked about (`check_docstrings`, `check_function_length`,
`check_complexity`) DO already run inside it — `bin/lint.sh` calls all three, and the standalone
tasks are shortcuts for checking one rule without paying for all 14.

But the wider question found a real gap. Measured by diffing the pre-commit hook ids against
`bin/lint.sh`:

| Gate | pre-commit | `poe lint` | CI |
|---|---|---|---|
| `check-provenance` | yes | **no** | **yes** |
| `check-typing` | yes | **no** | no |
| `check-all-exports` | yes | **no** | no |
| `check-dtypes` | yes | **no** | no |
| `check-docs-sections` | yes | **no** | no |
| `hadolint` (Dockerfile) | yes | **no** | no |
| `check-unix-filenames` | yes | **no** | no |

⚠️ `check-provenance` is a CI job that `poe lint` does not run, so "green locally, red in CI"
is reachable today. **This predates the migration** — `make lint` had the same set, and this PR
ported `lint.sh` unchanged.

Correctly absent, do not "fix" these: `check-backlog-ledger` (branch-scoped — it diffs the index
against merge-base, not a tree lint), `check-clean-index` (a pre-push hook), `coverage-check` (a
test gate).

⚠️ `.vscode/settings.json` is NOT a third place to add them: it does not run scripts, it only
configures editor-integrated tools (ruff on save, Pylance strict). `.vscode/tasks.json` carries
commands, and lists a curated subset deliberately.

- [ ] File this as its own issue and close it there, NOT in this PR: adding 7 gates to
      `lint.sh` may turn the five-tier harness red, and debugging 7 unrelated gates inside a
      ~90-file migration is how a migration stops being reviewable. The fix is small; the
      verification is not.

## Defects the harness caught during the swap — each invisible from every other angle

1. **`[tool.poetry.requires-plugins]` broke `poetry install`** (see the decision section).
2. **`bin/lint_shell.sh` listed `tasks.sh` as a literal** beside its `find`. A missing literal
   makes shellcheck report "does not exist" and **fail**, rather than skipping — so deleting
   `tasks.sh` did not lint one file fewer, it killed the whole shell gate. Discovery is now
   find-only.
3. **An `E501` and an `ERA001`** in newly written template code, neither visible to the root
   `make lint`, because a tier lints with its OWN pinned ruff.

⚠️ **A whole class of stale docs surfaced, unrelated to poe but found by grepping for it.**
Several documented commands that NEVER existed in any tier Makefile: `make start` (×3),
`make init_venv`, `make db_setup_schema`, `make precommit_update`, `make corporate_ca`,
`make wheelhouse`, and `make test_feat MODULE=` (the target used `FEAT=`). Nobody could have
run any of them. That is the cost of prose describing an interface with nothing checking the
prose — and it is the argument for the gate proposed in blueprintx#237.
