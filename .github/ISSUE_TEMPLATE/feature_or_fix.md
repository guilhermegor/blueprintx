---
name: Feature or fix
about: Propose a change, with its expected file surface declared up front
title: ""
labels: []
---

<!--
Required when the issue carries the `state:blocked` label:
  - a `**Blocked by:**` line naming each blocker — an issue ref (`repo#N`) where one exists, or
    `decision: …` when the blocker is a choice nobody has made yet. "Blocked" with no named
    blocker is not a status, it is a question the board cannot answer.
    Full convention: docs/contributing.md ("Blocked work").
    Add the line under "What / Why" only when blocked, in the form:
    **Blocked by:** repo#N, repo#N — or decision: …

Machine-readable form of the rule above, read by the guard (keep it on one line):
issue-template-guard: require "**Blocked by:**" if-label state:blocked
-->

## What / Why

<!-- What should change, and why. -->

## File surface

<!--
     List every path (or glob) a PR closing this issue is expected to touch, one per line,
     inside the fence below. bin/ci/check_issue_scope.py reads this block at PR time and
     checks that the PR's changed files stay inside it — see docs/issue-scope.md for the full
     design (declaration format, the undeclared/no-linked-issue/API-unreadable cases, and the
     `surface-override:` commit trailer for a PR that must legitimately widen its surface).

     Not sure yet, or the change is exploratory? Leave the block empty or delete it — an issue
     with no declared surface does not block a PR that closes it (UNDECLARED-SURFACE is
     non-blocking by design), but a declared surface is what makes "can these two issues be
     dispatched in parallel?" a query instead of a guess.

     `*` matches across `/`, so `docs/*` and `docs/**` are equivalent — use whichever reads
     clearer.
-->

```surface
# path/to/file/or/dir/** — replace this line; a commented or empty block means undeclared
```
