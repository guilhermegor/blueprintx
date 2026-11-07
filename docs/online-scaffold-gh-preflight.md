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

`SCAFFOLD_GH_GRAPHQL_REQUESTS` (44) is the number of GraphQL requests the
real `gh` sends for a fresh online scaffold, and `SCAFFOLD_GH_GRAPHQL_BUDGET`
(90) is set from it: twice the measured number (88), rounded up. A run does its
own preflight, so a retry is a new run and needs no allowance of its own; the
2x covers `gh` sending more requests than measured (paginated `field-list`,
a larger account, a future `gh` version). The test fails when the budget drops
below `2 * SCAFFOLD_GH_GRAPHQL_REQUESTS`.

How it was measured (2026-11-07, `gh` 2.103.3), with no GitHub account touched:
a local HTTPS server that logs every `POST /api/graphql` and answers with
canned JSON was set as `GH_HOST` (`GH_ENTERPRISE_TOKEN` set, `SSL_CERT_FILE`
pointing at its self-signed certificate). The real `gh` binary and the real
scaffold functions then ran the online path in order: preflight probe, `gh repo
create`, the ten house labels, board find, board create, visibility, link, Status
options, the seven fields and the workflows read. Counting a `gh` shim instead
would only see the 17 invocations above, because the extra requests are sent
inside `gh` itself.

| Step | GraphQL requests |
|---|---|
| preflight probe (`gh api graphql`) | 1 |
| `gh repo create` | 2 |
| house labels (10 x `gh label create`) | 0 (REST) |
| `gh repo view` for the visibility default | 1 (not exercised by the run; its query was not logged) |
| `gh project list` | 2 |
| `gh project create` | 2 |
| `gh project edit` | 3 |
| `gh project link` | 4 |
| Status `field-list` x2 and the options mutation | 5 |
| `gh project field-list` (existing fields) | 2 |
| `gh project field-create` x7 | 21 |
| workflows read | 1 |
| Total | 44 (43 logged + the visibility read) |

The per-command cost is 1 to 4 requests, never the 3x assumed before. The run
does not cover the card-add path, `gh issue create` or a board with more than
100 fields, so the figure is for a fresh setup only. The fake server cannot
reproduce what the real API returns for large accounts, so the number is a
floor for the request shape, not a prediction for every account.

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
each moves one kind of card to Done (closed issues, merged pull requests), and says "not found under that name"
when a workflow is absent from the answer. It never stops the scaffold, and
it is the one read here that does not go through `gh_read`: the step is
advisory, so a failure prints the one-line instruction to enable both by hand,
with the cause from `gh_classify_failure` (rate, auth, network or other).
Workflows cannot be enabled through the API.

## Not covered yet

The `delete_branch_on_merge` setting, the `Cut 1.0.0` release issue and its board card keep their warn-and-print-the-
manual-command fallback.
