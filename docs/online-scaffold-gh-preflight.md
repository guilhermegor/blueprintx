# Online scaffold: gh preflight and fail-closed reads

When you choose GitHub, the scaffold makes permanent changes: it creates the
repo, the kanban board, its visibility, labels and fields. An incomplete
online scaffold is never an acceptable result, so the scaffold stops instead of
guessing.

## What happens

1. **Preflight.** Before `gh repo create`, `gh_preflight`
   (`bin/lib/gh_preflight.sh`) calls GraphQL (`{viewer{login}}`), REST
   (`gh api user`) and `gh api rate_limit`. A failed call, a blank login, or
   fewer GraphQL points left than `SCAFFOLD_GH_GRAPHQL_BUDGET` stops the run
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

The budget is in points, the unit `rate_limit` reports, not requests. One
`gh project field-list` request costs 101 points, because `gh` sends it with
`items(first:100)` and `fields(first:30)`, so a count of requests says little
about what a scaffold spends.

One full online scaffold spends about 560 points (the table sums to 563, the
3 points of the card-add board lookup sit inside the 2x margin), the
`SCAFFOLD_GH_GRAPHQL_COST` default in `bin/lib/gh_preflight.sh`, and `SCAFFOLD_GH_GRAPHQL_BUDGET` (1120)
defaults to twice that. Only a re-run of the command
re-enters preflight, so a user retry is a new run and needs no allowance of its
own. The scaffold libraries have no in-run retry loop; if one is added, each
retried `field-list` costs about 102 points, and the 2x margin absorbs it along
with the estimated rows below and a future `gh` version.

The test pins the sourced defaults to literals (`SCAFFOLD_GH_GRAPHQL_COST` is
560 and `SCAFFOLD_GH_GRAPHQL_BUDGET` is 1120, with overrides unset), so
changing either default fails it and forces this table to be re-read. It cannot
tell whether 560 still matches what GitHub charges.

The invocation count (`SCAFFOLD_GH_GRAPHQL_MEASURED` and
`SCAFFOLD_GH_GRAPHQL_SITES`) counts invocations and not points, so a change in
what one call costs passes it. A new `field-list` in the fresh-setup path
fails the test's `field-list == 3` check; one on the card-add path fails its
`field-list == 2` check. That test also sums the four `card add:` rows below
(213 points) and compares them with 102 points per `field-list`, 3 per
`project list` and 2 per other call, so editing either the table or the call
count alone fails it. Those prices are pinned in the test as well as here, so
re-pricing means changing both. The
`first:100` inside `gh` is not visible to a stub, so a price change is caught
only through those table rows.

`SCAFFOLD_GH_GRAPHQL_BUDGET` changed unit from calls to points. An old exported
value (for example `100`) is now about 5x too loose, so the preflight prints a
warning when the budget is below the cost; unset it or re-set it in points. It
stays a warning, not a stop, because a deliberately low budget is a legitimate
override.

Online scaffolds are run by a person with their own `gh` login, never under an
Actions `GITHUB_TOKEN` (1,000 points per hour, below the 1120 budget); CI only
runs the stubbed test.

The request counts were measured on 2026-11-07 with `gh` 2.103.3: a local HTTPS
server that logs every `POST /api/graphql` and answers with canned JSON was set
as `GH_HOST` (`GH_ENTERPRISE_TOKEN` set, `SSL_CERT_FILE` pointing at its
self-signed certificate), and the real `gh` binary and scaffold functions ran
the fresh-board path. Counting a `gh` shim instead would only see the 17
invocations above, because the extra requests are sent inside `gh` itself.

The prices were read the same day from the real API, read-only, on an existing
board: the queries were captured with `GH_DEBUG=api`, then sent with
`rateLimit{cost}` added. For `field-list` the charge was also confirmed from
`remaining`, which fell from 1289 to 1188. `UserOrgOwner` costs 1, `UserProject`
1, `UserProjects` 2 and `UserProjectWithFields` 101. The other requests are
priced at the API's minimum of 1 point, not read individually.

| Step | Requests | Points |
|---|---|---|
| preflight probe (`gh api graphql`) | 1 | 1 |
| `gh repo create` | 2 | 2 |
| house labels (10 x `gh label create`) | 0 (REST) | 0 |
| `gh repo view` for the visibility default | 1 | 1 |
| `gh project list` | 2 | 3 |
| `gh project create` | 2 | 2 |
| `gh project edit` | 3 | 3 |
| `gh project link` | 4 | 4 |
| Status `field-list` x2 and the options mutation | 5 | 205 |
| `gh project field-list` (existing fields) | 2 | 102 |
| `gh project field-create` x7 | 21 | 21 |
| workflows read | 1 | 1 |
| Fresh setup subtotal | 44 | 345 |
| card add: `project list` (board lookup) | 2 | 3 |
| card add: `project view` | 2 | 2 |
| card add: `field-list` x2 | 4 | 204 |
| card add: `item-add` and `item-edit` | 4 (estimated) | 4 (estimated) |
| `gh issue create` | 5 (estimated) | 5 (estimated) |
| Total | 61 (9 estimated) | 563 |

The fake-server run did not cover the card-add path or `gh issue create`, so
those request counts come from the per-command shape above and are marked
estimated. A board with more than 30 fields is outside the figure too. No real
scaffold has been run against a throwaway account: the totals are built from
measured prices, not read from one end-to-end run.

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
