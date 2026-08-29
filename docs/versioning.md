# **Versioning — the v1.0.0 entry bar**

BlueprintX is currently `v0.16.x`. Under `0.x` semver a breaking change bumps the
*minor* — that is what `feat(python-common)!` did to reach `v0.16.0` — so the project
can ship breaking changes indefinitely without ever confronting the major version.
This page is the deliberate, once-written answer to three questions: what does
`1.0.0` freeze, what must be true before it ships, and what changes about how
breaking changes are handled after it does. (Tracked as
[issue #243](https://github.com/guilhermegor/blueprintx/issues/243).)

Cutting the release itself is unrelated to this page: the version **is** the git
tag, entered once in the `Release` GitHub Action's `version` field — see the root
`CLAUDE.md` "Releasing / version bump" section. This page produces the decision;
`/release` executes it.

## What `1.0.0` is a promise about

BlueprintX's most consequential surface is not `blueprintx --version` — it is the
shape of every project it generates. That surface is too broad to freeze in one
step, so this page freezes a **specific, named subset** and states the rest as
explicitly open. Everything named below is the only thing a major version bump
(`2.0.0`, etc.) will ever be *about*.

**Frozen at `1.0.0`:**

1. **The CLI/menu surface** — the subcommands `new`, `preview`, `dev`, `dev-clean`,
   `dry-run`, and `--help` (via `blueprintx`, `make`, or `tasks.sh`), and their
   observable behavior (what each prompts for, what it writes). Adding a new
   subcommand is a minor change; renaming or removing one of these is major.
2. **The `skeleton.meta` discovery format** — the four required keys `language`,
   `display_name`, `description`, `scaffold`, and the contract that any directory
   under `templates/` carrying a valid one appears in the menu automatically
   (`bin/ci/validate_meta.sh` enforces the four keys today). Adding a new optional
   key is minor; removing or repurposing one of the four is major.

**Explicitly NOT frozen at `1.0.0` — recommendation, needs owner sign-off:**

3. **Everything inside `templates/`** — the generated project's internal layout,
   task names (`poe lint`, `poe unit_tests`), gate implementations, and config file
   formats. A scaffolded project is forked at scaffold time and never pulls
   updates from BlueprintX again — there is no live channel through which a later
   BlueprintX release can break an already-generated project. `1.0.0`'s major-bump
   guarantee is about compatibility over time for a consumer that stays connected
   to the thing being versioned; a forked-and-abandoned copy is not that consumer.
   ⚠️ This is the legitimate-but-not-inevitable answer the issue itself names — the
   alternative (freezing template layout too) is real but far more expensive, and
   is the option that becomes cheap only once
   [#109](https://github.com/guilhermegor/blueprintx/issues/109) (the template-drift
   doctor) exists to give a scaffolded project *some* way to detect and follow a
   later change. Until #109 lands, freezing template internals would freeze bug
   fixes with no way for existing projects to benefit either way. **Recommended:
   template internals stay free to change every release, including post-1.0; this
   is stated so users know a second scaffold of the same skeleton may look
   different from the first.**

## Entry-bar checklist

Every row is decidable — yes/no, not a feeling.

- [ ] **This page is published and linked from `README.md`.** Satisfied by the PR
      that lands this document.
- [ ] **`docs/` and `README.md` are audited against the code**
      ([#242](https://github.com/guilhermegor/blueprintx/issues/242)) — **BLOCKER**.
      The frozen contract above is worthless if the docs describing it are already
      stale at the moment of the freeze.
- [x] **Every currently shipped skeleton scaffolds and passes CI from a clean
      checkout**, verified on `main`: the 5 Python tiers via the `scaffold-lint-test`
      matrix (`bin/ci/scaffold_lint_test.sh`), `react-spa-webpack` via
      `typecheck-ts`, and all 6 via `dry-run-smoke`. Measured true on `main` as of
      2026-08-29 (`Scaffold Checks` workflow, latest run: success). **Not a
      blocker — already met; re-verify green at cut time.**
- [x] **Every gate that can block a merge carries a should-fail regression test**
      ([#111](https://github.com/guilhermegor/blueprintx/issues/111), closed in
      Wave A per `docs/backlog/issue-waves_20260823_145527.md`). **Not a blocker —
      already delivered; re-verify no regression before cutting.**
- [ ] **Wave C (en-US prose consistency —
      [#194](https://github.com/guilhermegor/blueprintx/issues/194),
      [#195](https://github.com/guilhermegor/blueprintx/issues/195),
      [#197](https://github.com/guilhermegor/blueprintx/issues/197),
      [#241](https://github.com/guilhermegor/blueprintx/issues/241),
      [#245](https://github.com/guilhermegor/blueprintx/issues/245),
      [#247](https://github.com/guilhermegor/blueprintx/issues/247)) is resolved,
      or explicitly deferred past 1.0.** Docs-only — does not touch the frozen
      contract, so **not a blocker** by this page's recommendation. **Needs owner
      sign-off**: some may consider a clean prose baseline part of what "1.0"
      signals, independent of the API freeze.
- [ ] **Wave D (ts-lib skeleton) ships, or its absence is accepted.**
      [#135](https://github.com/guilhermegor/blueprintx/issues/135) (npm OIDC
      publishing) is the one issue still open in that wave. Adding a *new*
      skeleton via `skeleton.meta` is additive by construction — it does not touch
      either item in the frozen contract — so this page recommends it is **not a
      blocker**. **Needs owner sign-off**: whether v1.0.0 should imply Python/TypeScript
      skeleton-count parity is a product call, not a compatibility one.
- [x] **The template-drift question is answered in one direction, in writing.**
      This page answers it: templates are outside the frozen contract (item 3
      above), so [#109](https://github.com/guilhermegor/blueprintx/issues/109) is
      not required to land first. **Not a blocker under this page's
      recommendation** — reopens if the sign-off above goes the other way.
- [x] **The post-1.0 breaking-change policy is decided.** See below. Satisfied by
      this page.

## Post-1.0 policy — recommendation, needs owner sign-off

Because only the CLI surface and the `skeleton.meta` format are frozen (item 3
above), the everyday source of breaking changes today — template internals —
**stays outside major-version accounting after 1.0 too**. A template-breaking
change keeps bumping the minor, exactly as `#236` did under `0.x`. Only a change
to one of the two frozen surfaces bumps the major.

This directly answers the issue's question about cadence: under this policy,
BlueprintX is **not** likely to reach `v4.0.0` within a year, because the volume
of change the project ships today (Waves G–Q) is almost entirely inside
`templates/`, which does not count. A major bump becomes a rare, deliberate event
— changing what `new`/`preview`/`dev` do, or changing what a `skeleton.meta` must
declare — not a byproduct of routine template maintenance.

**If the owner instead wants templates inside the frozen contract**, the policy
above does not hold: template changes would need to bump the major, the pace
above changes completely, and #109 becomes a prerequisite rather than a follow-up.
That is the fork in this decision with the largest downstream cost, which is why
it is called out explicitly rather than defaulted.
