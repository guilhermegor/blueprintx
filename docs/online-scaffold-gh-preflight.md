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
   (one line per missing scope). The header name is matched case-insensitively
   and the list is compared with all whitespace removed. Scopes are matched
   whole, so `read:project` does not satisfy `project`. `repo` is required even
   for a public repository, so a token with only `public_repo` is stopped.
   A fine-grained or app token reports no `X-Oauth-Scopes` header; the
   preflight then says the scopes are "not verified" and continues, because
   there is nothing to compare.
   The `workflow` scope depends on how the first push authenticates. The
   scaffold adds the remote as `git@github.com:<slug>.git`, so its push uses
   SSH and does not need it. `bin/promote_offline_to_online.sh` runs
   `gh repo create --source=.`, which follows the `git_protocol` gh setting;
   over HTTPS, GitHub rejects a push that adds `.github/workflows/*` without
   `workflow`, so the promoter requires `repo` and `workflow` unless
   `gh config get git_protocol -h github.com` is `ssh` (the per-host value gh
   itself uses). The promoter never sets up a board, so it does not require
   `project`.
   `project` is required by the scaffold even if you later decline the board:
   the board prompt comes after `gh repo create`, and a token that cannot
   create it would otherwise fail after the repository exists. To opt out, set
   `SCAFFOLD_GH_REQUIRED_SCOPES` to the scopes you accept, for example
   `SCAFFOLD_GH_REQUIRED_SCOPES=repo`, or to an empty value to skip the scope
   check entirely.
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
   one, then re-run. The check runs right after the preflight, before
   `gh repo create`, so a duplicate leaves nothing half-created; it runs even
   if you would later decline the board, because the title is the project's
   own. The same check runs again when the board is set up, and a stop at that
   point carries the "already exists on GitHub" advice of any mid-run stop.
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

`SCAFFOLD_GH_GRAPHQL_MEASURED` (17) is the number of GraphQL-backed `gh` calls
(`gh project ...`, `gh repo view`, `gh api graphql`) a fresh kanban setup makes.
`tests/test_scaffold_gh_preflight.sh` counts them against a stubbed `gh` and
fails when the number changes, which is the prompt to re-set the budget.

`SCAFFOLD_GH_GRAPHQL_BUDGET` (100) stays the conservative bound it was. The
count above plus the preflight call and `gh repo create` is 19; times 3, the
most GraphQL queries one `gh` command is assumed to send (owner lookup, object
lookup, mutation), plus 3 for one retried command, gives 60. That multiplier
has not been measured: `gh project` subcommands can send more than 3 queries
(owner fallback, paginated `field-list`), and a fresh-board run is only one of
the branches. The budget is therefore not lowered to 60 until `gh api
rate_limit` has been read before and after a real run on a throwaway account.
The test only requires the budget to stay at or above that computed 60.

`SCAFFOLD_GH_GRAPHQL_SITES` (16) counts the call sites in the scaffold
libraries; the same test fails when one is added without updating it.

The two numbers differ because they count different things. Of the 16 sites,
11 run on a fresh board and 5 (the card-add path: `project view`, two
`field-list` reads, `item-add`, `item-edit`) do not. One of the 11, the
`gh project field-create` in the field loop, runs 7 times (one per field), so a
fresh setup makes 11 - 1 + 7 = 17 calls.

The workflows read asks for `workflows(first:20)`. A real board lists 6
built-in workflows (read with `workflows(first:100){totalCount}` on 2026-11-07),
so 20 leaves room and no pagination is needed.

## Board workflows

After the fields are created, `scaffold_kanban_workflows` reads the board's
built-in workflows through GraphQL (`ProjectV2.workflows`, which exposes
`enabled`). It warns when "Item closed" or "Pull request merged" is off, since
moving cards to Done relies on both, and says "not found under that name"
when a workflow is absent from the answer. It never stops the scaffold, and
it is the one read here that does not go through `gh_read`: the step is
advisory, so a failure prints the one-line instruction to enable both by hand,
with the cause from `gh_classify_failure` (rate, auth, network or other).
Workflows cannot be enabled through the API.

## Not covered yet

The `delete_branch_on_merge` setting, the `Cut 1.0.0` release issue and its board card keep their warn-and-print-the-
manual-command fallback.
