# Gate discovery: git ls-files over filesystem walks (#331)

Root cause behind #331's symptom (54 orphan `.claude/worktrees/` copies inflating
`check_function_length.py --root .` from 316 to 14,961 files): 11 gates do their own
filesystem discovery (`rglob`/`os.walk`/`glob`), zero mention `.claude`, and only one
(`check_unix_filenames.sh`) used `git ls-files` — the form that needs no skip-list, since a
worktree's contents are never tracked by the main working tree.

Measured first, per instructions: `git ls-files` only sees TRACKED files, so blind migration
risks a silent coverage loss.

## Measurement table (measured against a real scaffolded mvc-service-native-db project, with
54 simulated orphan-worktree files seeded under `.claude/worktrees/`)

| Gate | Discovery scope | Files today | Files via git ls-files | Delta | Verdict |
|---|---|---:|---:|---:|---|
| `check_all_exports.py` | `src/**/__init__.py` (cwd-relative) | 10 | 10 | 0 | **Left unchanged** — never reaches `.claude` (sibling of `src/`) |
| `check_comment_language.py` | repo root, `PATH_ROOT.rglob("*")` (`__file__`-relative, not cwd) | 243 (with bloat) | 181 | 62 (all bloat, 0 real files lost) | **Migrated** |
| `check_docs_sections.py` | `docs/**/*.md` (cwd-relative) | 10 | 10 | 0 | **Left unchanged** — never reaches `.claude` |
| `check_docstrings.py` | `src/`, `tests/` (cwd-relative) | 104 | 104 | 0 | **Left unchanged** — never reaches `.claude` |
| `check_dtypes.py` | `src/**/*.py` (cwd-relative) | 50 | 50 | 0 | **Left unchanged** — never reaches `.claude` |
| `check_layer_imports.py` | `src/**/*.py` (cwd-relative) | 57 | 57 | 0 | **Left unchanged** — never reaches `.claude` |
| `check_provenance.py` | `src/**/*.py` (cwd-relative) | 57 | 57 | 0 | **Left unchanged** — never reaches `.claude` |
| `check_typing.py` | `src/**/*.py` (cwd-relative) | 50 | 50 | 0 | **Left unchanged** — never reaches `.claude` |
| `check_function_length.py` (OFF LIMITS — open PR) | repo root, `PATH_ROOT.rglob()` (`__file__`-relative) | 223 (with bloat) | 161 | 62 (all bloat) | **Read-only** — same shape as `check_comment_language.py`; recommend migrating once its PR lands |
| `check_test_copy_lists.py` (OFF LIMITS — open PR) | not measured (outside file surface) | — | — | — | **Read-only**, out of scope for this PR |

**Why seven gates show delta=0:** they resolve their discovery root as `pathlib.Path("src")` /
`Path("docs")` / `Path("tests")` **relative to cwd**, and `.claude/` is a *sibling* of `src/`
at the repo root, not a descendant of it. `rglob` starting inside `src/` structurally cannot
walk into `.claude/worktrees/`. Migrating these to `git ls-files` would trade a real
(if narrow) risk — an untracked, not-yet-`git add`-ed file under `src/` silently dropping out
of local `poe lint` runs before it's staged — for zero benefit against the bug #331 describes.
Not manufactured as a migration.

**Why two gates were migrated/flagged:** `check_comment_language.py` and (read-only)
`check_function_length.py` are the only two in this family whose `PATH_ROOT` resolves from
`__file__.parent.parent` — i.e. the **repo root itself**, an ancestor of `.claude/worktrees/`.
Those are exactly the ones the issue's own measurement (14,961 vs 316) was taken against.

## Work

- [x] Measure all 9 gates in scope (8 + read-only `check_function_length.py`) against a real
      scaffolded project with simulated orphan-worktree bloat.
- [x] Migrate `check_comment_language.py`'s `audit_paths()` from `PATH_ROOT.rglob("*")` to
      `git ls-files` (new `tracked_files()` helper). `TUPLE_SKIP_DIRS` kept as a pure POLICY
      filter (`docs/` locale, `fixtures/` verbatim bytes) — no `.claude` entry needed or added.
- [x] Update `tests/unit/test_comment_language_gate.py`: `git init`+commit the fixture repo in
      `test_skip_dirs_are_matched_relative_to_the_repo_not_the_filesystem` (an uncommitted
      `tmp_path` tree is invisible to `git ls-files` by construction); switch
      `test_audit_covers_every_supported_extension_anywhere_in_the_tree`'s general-property
      check from a raw `rglob` to `tracked_files()`; add
      `test_untracked_files_are_invisible_but_tracked_ones_are_not` as the should-fail witness.
  - 22/22 tests pass; `ruff check --config ruff.toml` and `check_function_length.py --root .`
    both clean on the changed files (from inside `templates/python-common/`, not the repo root
    — the root's ruff/`--config` combination produces false ERA001 positives via
    `per-file-ignores` path-matching, unrelated to this change).
- [ ] Once the PR holding `check_function_length.py` merges, migrate it the same way
      (`PATH_ROOT.rglob()` → `git ls-files`), reusing the same shape proven here.
- [ ] Once the PR holding `check_test_copy_lists.py` merges, measure and (if warranted)
      migrate it — not measured in this pass since it was off-limits.
- [x] Leave `check_all_exports.py`, `check_docs_sections.py`, `check_docstrings.py`,
      `check_dtypes.py`, `check_layer_imports.py`, `check_provenance.py`, `check_typing.py`
      unmigrated — measured
      delta=0, no benefit, real (if narrow) untracked-coverage risk.

Completed — kept as a record. #331 stays open: two off-limits gates remain unmigrated.

## Follow-up from the PR review, 2026-08-31

Two of four findings valid, both fixed; two rejected with measurement.

**Valid — the fixture's `env` dropped `PATH`.** `subprocess.run(["git", …], env=dict_env)` with a
bare dict removes `PATH`, and Python then resolves the executable through `os.defpath`, which is
only `/bin:/usr/bin`. Measured on this machine: `git` is `/usr/bin/git`, so it worked here and
would have kept working in CI — and a binary outside those two directories raises
`FileNotFoundError` before the fixture is ever built. That is Homebrew's `/opt/homebrew/bin/git`
and any custom install, so a contributor to a **generated** project hits it where we never would.
Fixed by starting from `os.environ` and overriding only the four identity values.

⚠️ Worth naming: the first attempt to explain this fix inline was a four-line comment, and
`ERA001` rejected it as commented-out code — correctly. The reasoning belongs here; the code
keeps a one-line pointer.

**Valid — the delta=0 count.** The table lists seven gates at delta 0; the prose said six and the
completed-work list omitted `check_docs_sections.py`. Both corrected.

**Rejected — "restore Ruff import order".** `ruff.toml` sets `force-sort-within-sections = true`,
which sorts `import X` and `from X import …` **together** by module name within a section. The
existing order (`importlib.util`, `pathlib`, `subprocess`, `sys`, `types`) is what that setting
produces, and `ruff check --config ruff.toml` reports **No issues found**. The finding inverted
the setting's meaning.

**Rejected — "split the combined discovery test".** The assertion is
`sorted(names) == ["ok.py"]`, a single exact equality that already covers both directions: the
tracked file must be present AND nothing untracked may appear. Splitting it into
`"ok.py" in names` plus `"bloat.py" not in names` is strictly **weaker** — the pair stops
catching a third, unexpected file, which exact equality catches by construction. The failure
message already names what leaked.
