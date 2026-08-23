# Poe the Poet migration + PR-1 bundle (#232, #235, #233, #211)

Created 2026-08-23. Tracks the two-PR migration of the Python tiers' command interface
(`Makefile` + `tasks.sh` → bootstrap + `poe`) and the three adjacent issues bundled into PR 1
because they share the same expensive verification (`bin/ci/scaffold_lint_test.sh` across all
five Python tiers) and the same scaffold copy-list surface.

## Shape

| PR | Content |
|---|---|
| **PR 1** (this branch, `refactor/poe-task-runner-232`) | #232 step 1 (extract recipe bodies to `bin/`) + #235 + #233 + #211 |
| **PR 2** | The actual swap: `poe_tasks.toml`, bootstrap decision, delete `Makefile`/`tasks.sh` |

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
- [x] Root `make lint` (mirrors CI) — 21/21 gates
- [x] The harness earned its keep on this very PR: it caught an `E501` in the new test that the
      root `make lint` cannot see, because a tier lints with its OWN pinned ruff

## PR 2 — the swap (not started)

- [ ] Prove `poe` installs and runs on Windows/Git Bash behind the TLS proxy **before** porting;
      if it does not, reopen the comparison rather than pushing through
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
- [ ] `poe_tasks.toml` in `templates/python-common/`, venv-side targets ported
- [ ] Decide what happens to bootstrap (`init`, `venv`, `ensure_env`, `precommit`,
      `update_venv` create the venv, so they cannot run inside it) and write the answer down
- [ ] Update every caller: `.pre-commit-config.yaml`, CI workflows invoking `make`,
      `bin/help.txt`, `docs/`, and `bin/ci/scaffold_lint_test.sh`
- [ ] Delete `Makefile` + `tasks.sh` from the Python tiers, or state plainly why one stays
