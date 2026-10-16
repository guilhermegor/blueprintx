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
- [~] chore/comment-strip-slice4-304 4 TypeScript and Bash families: `ts-common`, `ts-lib`, `react-spa-webpack`, `bash-cli` (49 files, 891 lines)
- [ ] 5 `templates/python-common/src` and `templates/common` (55 files, 1027 lines)
- [ ] 6 Python skeletons: `ddd-*`, `mvc-*`, `api-*`, `lib-minimal` (78 files, 1133 lines)
- [ ] 7 `templates/python-common` config and workflows (35 files, 1401 lines)
- [ ] 8 `templates/python-common/tests` (55 files, 931 lines)
- [ ] 9 `templates/python-common/bin`, the gates themselves (66 files, 2113 lines)
- [ ] Z delete the superseded rules in `CLAUDE.md` and `templates/python-common/CLAUDE.md`, drop the
  baseline and flip the gate to strict zero tolerance

## Rulings in force

- A heredoc body that a scaffold writes into a generated file is output, never a comment.
- Short notes with no natural home go in `docs/decision-records.md`.
- Distill long blocks; do not move them verbatim.
- Generated projects ship their own rationale in their own docs layer.
- Step 1b (each scaffold writes a baseline so generated projects start with the ratchet on) is not
  merged yet; slice Z makes it moot by flipping the default.
