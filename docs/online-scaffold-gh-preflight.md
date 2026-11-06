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
and an existing `<project> kanban` board is completed, not duplicated: a re-run
re-applies its visibility, link and Status options and creates only the missing
fields. `gh repo create` is not idempotent: if the stop
happened after the repo was created, finish the remaining steps by hand or use
[Offline to Online](offline-to-online.md).

## The GraphQL budget

`SCAFFOLD_GH_GRAPHQL_MEASURED` (17) is the number of GraphQL-backed `gh` calls
(`gh project ...`, `gh repo view`, `gh api graphql`) a fresh kanban setup makes.
`tests/test_scaffold_gh_preflight.sh` counts them against a stubbed `gh` and
fails when the number changes, which is the prompt to re-set the budget.

`SCAFFOLD_GH_GRAPHQL_BUDGET` (60) is that count plus the preflight call and
`gh repo create` (19), times 3, the most GraphQL queries one `gh` command sends
(owner lookup, object lookup, mutation). The count is measured by call; the
multiplier is a bound, not a live measurement: no throwaway account was
available, so confirm it with `gh api rate_limit` before and after a real run.

`SCAFFOLD_GH_GRAPHQL_SITES` (16) counts the call sites in the scaffold
libraries; the same test fails when one is added without updating it.

## Board workflows

After the fields are created, `scaffold_kanban_workflows` reads the board's
built-in workflows through GraphQL (`ProjectV2.workflows`, which exposes
`enabled`). It warns when "Item closed" or "Pull request merged" is off, since
moving cards to Done relies on both. It never stops the scaffold: if the read
fails, it prints the one-line instruction to enable both by hand. Workflows
cannot be enabled through the API.

## Not covered yet

The `delete_branch_on_merge` setting, the `Cut 1.0.0` release issue and its board card keep their warn-and-print-the-
manual-command fallback. Two boards with the same title still warn and
continue without a board, and the `project` token scope is not checked before
the repo is created.
