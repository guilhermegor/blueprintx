# Issue scope: declaring and enforcing a file surface

blueprintx#314. Turns the hand-written "collision map" every dispatched agent used to get —
a prose list of files currently in flight, reconstructed from memory on every dispatch, never
checked — into something a gate can read and verify at PR time.

## The problem this replaces

Two agents given `isolation: "worktree"` once ended up touching the same directory: one
agent's files were wiped mid-task, an empty commit reported full success, and a foreign commit
leaked onto another agent's branch. The prose collision map that was supposed to prevent this
was reconstructed by hand every dispatch, only as good as the orchestrator's recall, and
nothing verified an agent actually respected it.

## Declaration format: a fenced `surface` block, not a `scope:*` label

The issue's own proposal was a `scope:<area>` label (`scope:templates-python`, `scope:bin-ci`,
…). This gate uses a fenced code block in the issue body instead:

````markdown
```surface
bin/ci/check_issue_scope.py
docs/issue-scope.md
```
````

One path or glob per line. A path matches an entry either exactly, or via shell-style
wildcards (`fnmatch`) — `*` already spans `/`, so `docs/*` and `docs/**` match the same set;
either spelling is accepted for readability. Lines starting with `#` are comments.

**Why not the label.** A label needs a second artifact to mean anything: a taxonomy file
mapping each `scope:*` value to the paths it actually names, kept in sync with the milestone
structure by hand. The issue's own scope section already names the risk: *"backfilling ~40
issues by hand is where this quietly dies."* A fenced block sidesteps both problems — it is
the declaration (no separate mapping to maintain), and it is opt-in per issue rather than a
mass rewrite of every open issue on day one. It also mirrors a pattern already live in this
repo's own dispatch loop: the orchestrator's `dispatch-claims.tsv` is exactly `<issue>\t<path>`
lines, one path per claim.

Labels remain available for coarse routing (`oracle:*`, `hitl`/`afk`) where "which bucket" is
the question. This gate answers a different, finer question — "which exact paths" — where a
label's blast-radius granularity is the wrong shape.

## What the check compares

The set of files a PR touches must be a subset of the union of the `surface` patterns declared
on every issue the PR closes (`closingIssuesReferences` — not the PR body's "Closes #N" text,
the resolved GitHub reference, since only that reflects whether the PR actually targets the
default branch and therefore whether the reference is live at all).

## Call budget

This session's GitHub API quota was exhausted three times in one day by checks that re-query
every open PR and branch. This gate is deliberately frugal: the PR's changed files, its
`closingIssuesReferences`, and its commits (for the override trailer, below) come back from
**one** `gh pr view --json files,closingIssuesReferences,commits` call — `closingIssuesReferences`
has no REST equivalent, so this is the one call that must go through `gh`'s GraphQL-backed
`--json` rather than `gh api`. Each linked issue's body is then one plain REST call
(`gh api repos/<repo>/issues/<n>`) — typically one issue per PR in this repo's workflow, so the
typical run costs 2 calls total.

## Decision table

| Situation | Result | Blocks the PR? |
|---|---|---|
| PR closes no issue | `not applicable` | No |
| Every closed issue declares a surface; files ⊆ union | `scope OK` | No |
| Every closed issue declares a surface; a file falls outside, no override | violation named | **Yes** |
| Same, but a commit carries `surface-override: <reason>` | `OVERRIDDEN` + reason logged | No |
| At least one closed issue has **no** `surface` block | `UNDECLARED-SURFACE` | No (see below) |
| The GitHub API is unreadable (rate limit, auth, network) | `UNKNOWN` | **Yes** |

## Strictness: "payable", not "zero current violations"

The issue itself asks which criterion set the strictness, because both look like measurement
and answer different questions. This gate picked **payable**: a linked issue with no declared
surface does not block the PR. The alternative — treat an undeclared surface as a violation —
would fail every open PR the day this gate merged, since none of the ~40 issues open at the
time had a `surface` block yet (including blueprintx#314 itself). Enforcement activates per
issue, the moment that issue's body gets a `surface` block; there is no separate backfill step
to run first.

**Known follow-up, stated rather than fabricated:** the issue asks to run this gate against
`origin/main~20..origin/main` and report how many merged PRs it would have flagged. That run
needs a `surface` block on each of those merged PRs' issues to mean anything (see the
strictness note above) — none exist yet, so the honest number today is "0 issues have a
declared surface, so 0 PRs would be flagged and the number says nothing about the gate's real
strictness." Re-run it once a meaningful slice of issues have opted in.

## The override

A PR that must legitimately widen its surface says so, rather than being silently blocked —
matching this repo's existing `gate-change-ok:` convention for a gate a PR must weaken. Add a
commit trailer:

```
surface-override: <reason the PR must touch files outside its issue's declared surface>
```

on any commit in the PR. The gate still reports every out-of-surface file, but exits 0 with the
reason printed alongside them — an override is loud, not invisible.

## Unreadable API: UNKNOWN, never a silent pass

If `gh` fails (rate limit, auth, network, malformed JSON) at any point — fetching the PR
snapshot or an issue body — the check prints `::error::UNKNOWN — could not verify issue scope:
<reason>` and exits non-zero. This follows the same rule `bin/ci/check_actions.sh` already
applies to a missing `actionlint`: a gate that goes quiet under a real failure and reports
green is a gate reporting its own blindness as OK. An unreadable API is never treated as "no
violation found."

## Feeding this back into dispatch

Once a meaningful number of issues carry a `surface` block, "are issue A and issue B safe to
dispatch in parallel" becomes `issue_surface(A) ∩ issue_surface(B) == ∅` — a query against two
issue bodies, not a prose judgment reconstructed from memory. That wiring (generating an
agent's collision map from declared surfaces) is out of scope for this change; it is a natural
next step once enough issues declare a surface for the intersection to be meaningful.

## Not in scope here

- The `scope:*` label taxonomy from the issue's original proposal, and backfilling it onto
  existing issues — superseded by the fenced-block design above.
- Wiring this gate into `.pre-commit-config.yaml` — a pre-commit hook has no PR or linked-issue
  context to check against (it runs on a local working tree, not a PR), so there is nothing for
  it to enforce locally beyond what this PR-time gate already covers.
- Shipping a copy of this gate into `templates/python-common/bin/` for generated projects. It
  reads *this* repo's own dispatch conventions (`closingIssuesReferences`, the `surface` block
  convention) via `GITHUB_REPOSITORY`/`PR_NUMBER`, the same shape as
  `templates/common/bin/check_review_threads.py` — so it travels the same way, if/when a
  generated project adopts the same per-issue dispatch model. Until then, a second copy nothing
  exercises is exactly the drift `check_test_copy_lists.py`/`check_actions.sh` exist to catch.
