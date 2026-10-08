# **Contributing**

How to contribute to BlueprintX itself (the scaffolding tool).

> **See also:** the repository's root `CONTRIBUTING.md` holds the authoritative branch/PR and
> commit-message policy · [CLI Reference](cli-reference.md).

---

## Development setup

```bash
make init          # bootstrap the venv + install pre-commit hooks
make lint          # run all pre-commit hooks across the repo (mirrors CI)
```

The root repo's pre-commit mirrors `.github/workflows/scaffold_checks.yml`: the shared checks
live in `bin/ci/*.sh` and both the workflow and the hook call them — one home per check.

## Adding a new skeleton

1. Create `templates/<name>/` with the skeleton's files.
2. Add a `skeleton.meta` descriptor (`language`, `display_name`, `description`, `scaffold`).
3. Write a scaffold script under `bin/scaffold/`.
4. The interactive menu discovers it automatically — no change to `blueprintx.sh`.
5. Add the install/usage notes to `README.md` and a docs page under `docs/`.

## Cross-language quality parity

A quality decision (a lint rule, a gate, a coding convention) applies to **every** scaffolded
language unless that language's own community standard overrides it — in which case the
community standard wins. Parity is by prohibited construct, never by a copied number. These
decisions are written in `CONTRIBUTING.md`/`README.md`/docs, never as a code comment (QA
suppressions like `noqa` are exempt). See the root `CONTRIBUTING.md` → "Cross-Language Quality
Parity" for the full rule, worked examples, and the dated Python-vs-TypeScript gate table.

## Shared template sources

`templates/python-common/` (shared Python tooling), `templates/ts-common/` (shared TypeScript
tooling), and `templates/common/` (language-agnostic assets) are the single sources of truth —
change them there and every skeleton inherits the change on the next scaffold run.

The per-project Claude Code guidance follows the same rule. `templates/common/CLAUDE.md` is the
one home for what every skeleton shares (the boundary rules, data-handling guardrails, naming
and file-naming conventions, tooling summary, runtime type-checking notes, project-memory
rule); it ships to a generated project as `.claude/CLAUDE.md`, and each skeleton's root
`CLAUDE.md` keeps only what is specific to that tier plus a pointer. Measured before the split
(blueprintx#549, shared non-blank lines over the smaller file): `mvc-service-native-db` vs
`mvc-service-orm-db` 89%, `ddd-service-native-db` vs `ddd-service-orm-db` 85%, any DDD tier vs
any MVC tier 60–66%. After it: 65%, 62% and 20–28% — what remains is the architecture each
pair genuinely shares (layer tables, key abstractions), which the issue classifies as
per-skeleton. Edit a shared convention in `templates/common/CLAUDE.md`, never in one skeleton's
root file, where the change would reach one tier and silently miss the rest.

## Pull requests

Branch off `main` using the CONTRIBUTING prefix policy (`feat/…`, `fix/…`, …), keep `make lint`
green, and fill out the PR template. Direct commits to `main` are blocked by pre-commit.

## Blocked work

Work that cannot start because an upstream is unfinished is marked on the issue and on the
kanban board, so it is obvious when to stop here and go finish the upstream.

**Convention.** An issue that cannot start carries the `state:blocked` label and a
`**Blocked by:**` line at the start of a body line, naming each blocker as `repo#N`, or as
`decision: <why>` when the blocker is a choice nobody has made yet. The same convention is used in
`greenfield` (`project-seed.md`), so every repo reads it the same way. The
[issue template](https://github.com/guilhermegor/blueprintx/blob/main/.github/ISSUE_TEMPLATE/feature_or_fix.md)
carries the line plus the machine-readable `issue-template-guard:` directive that makes a
`state:blocked` issue without it get rejected (guard: `issue_template_guard.sh` in `dotfiles-dev`,
`ai_clients/claude/hooks/`).

**Why a convention and not only GitHub's native `blocked_by`.** The native relationship is
same-repo only, so a blocker in another repository cannot use it. Where it does apply, nothing
propagates it: GitHub resolves the dependency when the blocker closes, but the board Status, the
label and the `Blocked by` field sit still until the reconciler (`roadmap_unblock.sh` in
`dotfiles-linux-dev`) re-reads them. Where the blocker is in the same repository, mirror it as a native relationship too.

**Rules.**

- Name the specific upstream issue whenever one exists. Link the terminal issue ([#601](https://github.com/guilhermegor/blueprintx/issues/601)) only when
  the blocker really is "not 1.0 yet" — the reconciler clears on the *named* issue, so pointing
  everything at that issue holds work that is in fact ready.
- A `decision:` blocker is never auto-cleared; only a person removes it. That is deliberate.
- A board Status alone is not durable: the reconciler clears any item it reads as blocked by
  nothing. Each blocked item needs the label plus the `**Blocked by:**` body line (the issue
  template guard rejects a `state:blocked` issue without it). A native `blocked_by` entry is an
  additional mirror where supported, never a replacement for the body line.

**Board.** The kanban board's `Status` options read
`Blocked | Backlog | Ready | In progress | In review | Done` (`Blocked` first, as on every board
this convention reaches), with a `Blocked by` text field.

!!! warning "Pin every option `id` when editing the Status field"
    `updateProjectV2Field` replaces the entire option set, and an option sent without its
    existing `id` is minted as a new one — every item's stored value then dangles and reads
    empty. Adding `Blocked` to another board this way wiped all 271 item Statuses in one call.
    Snapshot first (`gh project item-list <n> --owner <o> --limit 300 --format json`), send
    every option with its existing `id` (only the new `Blocked` has none), pass the payload as a
    `{query, variables}` body via `gh api graphql --input <file>`, then diff per item id against
    the snapshot.

## Releasing

The version is the git tag — cut a release from the **Release** GitHub Action (enter the
version once). See the [FAQ](faq.md#how-is-blueprintx-itself-versioned).
