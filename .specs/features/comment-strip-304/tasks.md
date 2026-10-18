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
- [~] chore/comment-strip-slice6-304 6 Python skeletons: `ddd-*`, `api-*`, `lib-minimal` (51 files, about 880 lines)
- [x] 6b (PR #823) Python skeletons: `mvc-service-native-db`, `mvc-service-orm-db` (split from 6 at the 90-file ceiling, 40 files)
- Dependency met: #826 (ship the zero-comment ratchet to every generated project) merged as #828; slices 7 to 9 and Z may proceed. Whatever they strip must be stated as dehydrated into the right layer (SECURITY, README, CONTRIBUTING or docs).
- [x] 7a (PR #841) `templates/python-common/.github` workflows and `dependabot.yml` (10 files, 569 lines); rationale in `docs/decision-records.md`
- [x] 7b (PR #843) `templates/python-common` config files (`ruff.toml`, `mypy.ini`, `poe_tasks.toml`, `.pre-commit-config.yaml`, dotfiles; 22 files, 889 lines)
- [x] 8 (PR #844) `templates/python-common/tests` (54 files, 808 lines; `test_review_threads_gate.py` is left to #837); rationale in `docs/decision-records.md`
- [x] 8b (PR #854) `templates/python-common/tests/unit/test_review_threads_gate.py` (123 lines), left out of slice 8 while #837 owned it
- [ ] 9 `templates/python-common/bin`, the gates themselves (66 files, 2113 lines)
- [x] 9a (PR #845) `templates/python-common/bin` shell scripts and `lib/*.sh` (33 files, 1287 lines); oracle: `shfmt -mn` output identical before and after. Slice 9 is split 9a shell, 9b Python gates, 9c the comment-budget gate itself plus its banner exemption
- [~] chore/comment-strip-slice9b-304 9b `templates/python-common/bin` Python gates and `lib/*.py` (32 files, 779 lines); the AST of every module is identical before and after. Slice 9 is split 9a shell, 9b Python gates, 9c the comment-budget gate itself plus its banner exemption
- [x] 9c (PR #847) `check_comment_budget.py`, `comment_budget_allowlist.txt`, `required-checks.txt` (3 files, 108 lines); behaviour unchanged (AST, parsed allowlist and check names identical)
- [ ] 9d delete the test-section banner exemption (`STR_TEST_SECTION_RULE`, `is_exempt_section_banner`, `is_test_module`) with a should-fail test; must follow slice 8, which removes the banners it exempts
- [ ] Z delete the superseded rules in `CLAUDE.md` and `templates/python-common/CLAUDE.md`, drop the
  baseline and flip the gate to strict zero tolerance

## Rulings in force

- A heredoc body that a scaffold writes into a generated file is output, never a comment.
- Short notes with no natural home go in `docs/decision-records.md`.
- Distill long blocks; do not move them verbatim.
- Generated projects ship their own rationale in their own docs layer.
- Step 1b (each scaffold writes a baseline so generated projects start with the ratchet on) is not
  merged yet; slice Z makes it moot by flipping the default.
