# Online scaffold: gh preflight and fail-closed reads

When you choose GitHub, the scaffold makes permanent changes: it creates the
repo, the kanban board, its visibility, labels and fields. An incomplete
online scaffold is never an acceptable result, so the scaffold stops instead of
guessing.

## What happens

1. **Preflight.** Before `gh repo create`, `gh_preflight`
   (`bin/lib/gh_preflight.sh`) calls GraphQL (`{viewer{login}}`), REST
   (`gh api user`) and `gh api rate_limit`. A failed call, a blank login, or
   fewer GraphQL calls left than `SCAFFOLD_GH_GRAPHQL_BUDGET` stops the run
   before anything is created.
2. **Cause and wait.** The stop message names the cause and when to retry:
    - rate limit: the reset time as a duration and an absolute time, for
      example `retry in 14 min, after 00:34Z`; a secondary limit uses the
      `Retry-After` value; `unknown, retry later` when neither is available;
    - authentication: run `gh auth login` (or `gh auth refresh -s project`);
    - network: check the connection to `api.github.com`.
3. **Fail-closed reads.** A failed read that feeds the board visibility, the
   owner kind (user or organization) or the GitHub login stops the scaffold.
   The default board visibility ("same as repo") is never `PUBLIC` after a
   failed read.
4. **Mid-run failures stop too.** A house label, board edit, link, Status
   option, project field, or default-branch edit
   failure after the preflight stops with the same message instead of a
   warning.

## Retrying

Re-run the same command once the wait has passed. House labels use `--force`,
and an existing `<project> kanban` board is detected and skipped, so a re-run
does not duplicate them. `gh repo create` is not idempotent: if the stop
happened after the repo was created, finish the remaining steps by hand or use
[Offline to Online](offline-to-online.md).

## The GraphQL budget

`SCAFFOLD_GH_GRAPHQL_BUDGET` (100) is a conservative upper bound, not a live
measurement. `SCAFFOLD_GH_GRAPHQL_SITES` (14) counts the `gh project`,
`gh repo view` and `gh api graphql` call sites in the scaffold libraries;
`tests/test_scaffold_gh_preflight.sh` fails when a call site is added without
updating it, which is the prompt to re-check the budget.

## Not covered yet

The `delete_branch_on_merge` setting, the `Cut 1.0.0` release issue and its board card keep their warn-and-print-the-
manual-command fallback, and the built-in board workflows are not read.
