# Comment strip (blueprintx#304)

Tracker for the sweep ruled on 2026-10-11 and 2026-10-14: apart from QA suppressions, every
comment moves to a docs layer and nothing is left behind in the code. Spike and rulings:
issue #304 comments. Slices are serial, low risk first; each one lowers
`comment_budget_baseline.txt` in its own PR and stays under 90 files.

Baseline at spike time: 422 files, 11665 comment lines, plus about 770 lines in file types the
gate did not read until P0.

## Tasks

- [x] P0 (PR #785): gate reads every file type, `.env.example` keys-only with
  `docs/configuration.md` per tier and the key-sync gate
- [x] 1 (PR #789) root `.github/`, root `tests/`, root dotfiles, `Makefile`, `mkdocs.yml`, root `.env.example` (38 files, 1205 lines)
- [x] 2 (PR #805) root `bin/` excluding `bin/scaffold/` (36 files, 1537 lines); also fix the truncated step name
  `Install npm dependencies (npm ci enforces the committed lockfile,` in `scaffold_checks.yml`
  (` #464` was parsed as a YAML comment)
- [x] 3 (PR #810) `bin/scaffold/*.sh`, with a before/after scaffold diff of all tiers as the oracle (9 files, 1336 lines)
  - The diff caught two defects in the first strip: `#` lines that a multi-line `sed` or `printf`
    writes into the generated `pyproject.toml` were removed (they are output, so they stay), and
    blank lines inside generated Python were collapsed. A line that starts inside a quoted
    string or a heredoc is now kept, and blank lines are dropped only outside those regions.
- [x] 4 (PR #814) TypeScript and Bash families: `ts-common`, `ts-lib`, `react-spa-webpack`, `bash-cli` (49 files, 891 lines)
- [x] 5 (PR #820) `templates/python-common/src` and `templates/common` (55 files, 1027 lines)
- [x] 6 (PR #822) Python skeletons: `ddd-*`, `api-*`, `lib-minimal` (51 files)
- [x] 6b (PR #823) Python skeletons: `mvc-service-native-db`, `mvc-service-orm-db` (split from 6 at the 90-file ceiling, 40 files)
- Dependency met: #826 (ship the zero-comment ratchet to every generated project) merged as #828.
- [x] 7a (PR #841) `templates/python-common/.github` workflows and `dependabot.yml` (10 files, 569 lines)
- [x] 7b (PR #843) `templates/python-common` config files: `ruff.toml`, `mypy.ini`, `poe_tasks.toml`, `.pre-commit-config.yaml` and 18 dotfiles (22 files, 889 lines)
- [x] 8 (PR #844) `templates/python-common/tests` (54 files, 808 lines); `tests/CLAUDE.md` no longer mandates comment banners
- [x] 8b (PR #854) `test_review_threads_gate.py` (123 lines), left out of slice 8 while #837 owned it
- [x] 9a (PR #845) `templates/python-common/bin` shell scripts and `lib/*.sh` (33 files, 1287 lines); oracle: `shfmt -mn` output identical before and after
- [x] 9b (PR #846) `templates/python-common/bin` Python gates and `lib/*.py` (32 files, 779 lines); oracle: AST identical
- [x] 9c (PR #847) `check_comment_budget.py`, `comment_budget_allowlist.txt`, `required-checks.txt` (108 lines)
- [x] 9d (PR #862) delete the test-section banner exemption with a should-fail test
- [x] 10 (PR #858) residuals: `templates/python-common/optional` and the OTel pin comment lines that six scaffolds appended to a generated `pyproject.toml`
- [x] Z (this PR) superseded rules deleted: stale pointers to comments that no longer exist
  (`CLAUDE.md`, `templates/python-common/CLAUDE.md`, `templates/python-common/src/config/CLAUDE.md`,
  the three native-DB `AGENTS.md` that said a `.sql` opens with a header comment,
  `templates/ts-common/CLAUDE.md`, `templates/ts-lib/AGENTS.md`, `docs/complexity-ceilings-measured.md`,
  `docs/secret-scanning.md`)

## Rulings in force

- A heredoc body that a scaffold writes into a generated file is output, never a comment.
- Short notes with no natural home go in `docs/decision-records.md`.
- Distill long blocks; do not move them verbatim.
- Generated projects ship their own rationale in their own docs layer.
- Step 1b shipped as #828: each scaffold writes a baseline so generated projects start with the
  ratchet on.
- The strict state is an empty baseline. The ratchet treats a file absent from the baseline as 0,
  so `comment_budget_baseline.txt` holding only its `scope` row is zero tolerance: any new
  comment outside the allowlist fails. The file stays (the hooks run `--require-baseline`) instead
  of being deleted, so no hook, workflow or scaffold helper changes.

## Completed — kept as a record

The sweep finished with every slice above merged. Measured on the merged tree with the gate's own
tool: `check_comment_budget.py --root . --write-baseline` writes 0 files and 0 comment lines (from
11665 lines in 422 files at spike time). `make verify_tiers`, the otel and storage opt-in scaffolds
and `pre-commit run --all-files` pass. Kept per the backlog rule: do not delete a finished tracker.
