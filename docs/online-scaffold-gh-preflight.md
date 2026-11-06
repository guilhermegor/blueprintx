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
   The same preflight reads the token scopes (`gh api -i user`, header
   `X-Oauth-Scopes`) and requires every scope in `SCAFFOLD_GH_REQUIRED_SCOPES`
   (`repo project`): `repo` for the repository, labels, issues and secrets,
   `project` for `gh project`. A missing scope stops the run before
   `gh repo create`, names the scope, and prints `gh auth refresh -s <scope>`
   (one line per missing scope). Scopes are matched whole, so `read:project`
   does not satisfy `project`. A fine-grained or app token reports no
   `X-Oauth-Scopes` header; the preflight then says the scopes are "not
   verified" and continues, because there is nothing to compare. The `workflow`
   scope is not required: it matters only when `git push` runs over HTTPS with
   the gh token, not for any `gh` call.
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
4. **Duplicate board titles stop.** Two boards titled `<project> kanban` stop
   the scaffold and print both board URLs. The scaffold never guesses which one
   to use and never finishes with no board linked. Delete or rename all but
   one, then re-run. The repository already exists at that point, so the stop
   message carries the same "already exists on GitHub" advice as any mid-run
   stop.
5. **Mid-run failures stop too.** A house label, board edit, link, Status
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

`SCAFFOLD_GH_GRAPHQL_BUDGET` (100) is a conservative upper bound, not a live
measurement. `SCAFFOLD_GH_GRAPHQL_SITES` (15) counts the `gh project`,
`gh repo view` and `gh api graphql` call sites in the scaffold libraries;
`tests/test_scaffold_gh_preflight.sh` fails when a call site is added without
updating it, which is the prompt to re-check the budget.

## Not covered yet

The `delete_branch_on_merge` setting, the `Cut 1.0.0` release issue and its board card keep their warn-and-print-the-
manual-command fallback, and the built-in board workflows are not read.
