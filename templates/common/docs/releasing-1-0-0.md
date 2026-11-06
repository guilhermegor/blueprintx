# Releasing 1.0.0

1.0.0 is the moment this library promises its public API. Until then the 0.x rules apply: a
breaking change is a MINOR bump, a feature or fix is a PATCH. From 1.0.0 on, full semver
applies. Two things must be true at that moment and are easy to get wrong by hand: the
backlog is done, and the docs describe the code that actually ships.

## The path

1. The **Cut 1.0.0** issue is opened for you when the scaffold creates the GitHub repo, from the
   issue template, `state:blocked` and blocked by every other open issue (on the kanban, status
   `Blocked`). If the repo was not created by the scaffold, open it by hand from the issue
   template with the `state:blocked` label and the exact title `Cut 1.0.0`.
2. Implement the backlog. An issue that will not make 1.0.0 gets the `post-1.0` label, set by
   the owner (the scaffold creates the label; otherwise `gh label create post-1.0`), so it is deferred on the record rather than dropped.
3. Work the issue's checklist: the docs audit, runnable examples, the 1.x supported-versions
   table in `SECURITY.md`, the public-API freeze (audit the exported names; removing one after
   1.0 is a 2.0), a `## 1.0.0` CHANGELOG section stating the API guarantee, and every open
   pull request merged, closed, or explicitly deferred past 1.0 by the owner, then the rehearsal and publish. Python projects also flip the classifier to
   `Development Status :: 5 - Production/Stable`, check that `requires-python` (Poetry's `python` constraint) and one Python
   classifier per version of the `tests.yaml` matrix agree, and confirm `py.typed` is in the
   built wheel.
4. After the release, switch the documented version policy to full semver and, for a project
   that deploys docs with mike, confirm the `latest` alias moved to 1.0.

## The release gate

The release workflow runs `bin/check_release_gate.py` before it publishes. It applies only
when the requested MAJOR is at least 1 and the latest published version is 0.x. In that case
it lists the open issues and fails while any lacks the `post-1.0` label, naming each one.

- Pull requests are not counted, and neither is the **Cut 1.0.0** issue itself. This is a
  decision, not an omission: failing on open PRs would let a standing Dependabot PR or a
  `post-1.0` feature branch block every release, and the gate has no label to exempt a PR
  with. The smaller blast radius is to keep the gate on issues and put "every open PR
  merged, closed, or deferred past 1.0" on the **Cut 1.0.0** checklist, where the owner
  judges each PR. BlueprintX's own test
  suite pins that a lone open PR passes the gate.
- The issues are read through the GitHub REST API with the workflow token, read-only.
- If the API cannot be read, the gate fails closed: it blocks the release rather than guess.
- Every other bump, such as 0.4.0 to 0.5.0 or 1.0.0 to 1.0.1, is untouched.
- A first publish counts as coming from 0.0.0, so a project whose first release is 1.0.0 is gated too.

To pass, implement each named issue or label it `post-1.0`, then re-run the workflow.
