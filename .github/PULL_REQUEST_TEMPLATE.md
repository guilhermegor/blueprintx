## Description
**What**: Briefly summarize the changes (e.g., "Added react-spa-webpack skeleton").
**Why**: Explain the motivation (e.g., "To support TypeScript scaffolding").
**How**: Link to implementation details (e.g., "Added bin/scaffold/ts_react_app.sh and templates/react-spa-webpack/").

---

## Changes Made
**Added**:
- New skeleton / script: [Description].
- New template file: [Path].

**Updated**:
- Refactored [Script/Template] for [Reason].

**Fixed**:
- Issue #[Number]: [Brief description].

<!-- CLOSING KEYWORDS — GitHub closes the issue on merge ONLY in this exact shape.
     The line above LINKS the issue; it does not close it. Add one keyword line per issue:

       Closes #12
       Closes #13

     Two traps, both measured in this repo:
       * NO colon after the keyword. `Closes: #12` / `Fixes: #12` link but never close.
       * ONE keyword PER issue. `Closes #12, #13` closes only #12 — GitHub reads just the
         first item of a comma-separated list. Repeat it: `Closes #12, Closes #13`.

     Verify the EFFECT, not the text, once the PR exists:

       gh api graphql -f query='{repository(owner:"OWNER",name:"REPO"){pullRequest(number:N){
         closingIssuesReferences(first:20){nodes{number}}}}}' \
         --jq '.data.repository.pullRequest.closingIssuesReferences.nodes[].number'

     An empty or short list means the PR closes nothing (or not everything) on merge.
     `gh pr view --json closingIssuesReferences` can serve a STALE cache right after
     `gh pr edit`; the GraphQL read above is the reliable one. -->

---

## Testing
### Manual Testing
- **Dry-run**:
    - Steps: `make dry-run` → select [language] → select [skeleton]
    - Expected: Structure preview shown, no files created.
- **Full scaffold**:
    - Steps: `make dev` → select [language] → select [skeleton] → verify output in temp dir
    - Expected: Project created at expected path with correct files.

### Automated Testing
- **CI (this PR)**:
    - `lint-shell`: ShellCheck on `bin/**/*.sh` — Status: `OK/NOK`
    - `validate-meta`: skeleton.meta integrity — Status: `OK/NOK`
    - `docs-build`: MkDocs strict build — Status: `OK/NOK`
    - `dry-run-smoke`: all skeletons — Status: `OK/NOK`
    - `typecheck-ts`: tsc --noEmit — Status: `OK/NOK`
    - `spell-check`: codespell — Status: `OK/NOK`

**Not Applicable**:
- Explain (e.g., "Documentation-only change").

---

## Documentation
- **Docs site** (`docs/`): Added/updated [page].
- **CLAUDE.md**: Updated if scaffolding flow changed.
- **README**: Updated if new skeleton added.

---

## Additional Notes
**Dependencies**:
- Blocks/Depends on #[PR Number].

**Follow-up**:
- Tech debt: [Brief note].

**Reviewer Focus**:
- Pay attention to [specific files/logic].
