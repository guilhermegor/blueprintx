# **FAQ**

Common questions about using and extending BlueprintX.

> **See also:** [Get Started](get-started.md) · [CLI Reference](cli-reference.md) ·
> [Contributing](contributing.md).

---

## What is BlueprintX?

A Make + bash scaffolding tool that generates opinionated Python and TypeScript project
skeletons (DDD service, MVC service, minimal library, React SPA) with CI, pre-commit, tests,
and docs wired in. It is not a Python application — the Python code lives in `templates/` and is
copied into scaffolded projects.

## How do I scaffold a project?

`make new`, then answer the prompts (language → skeleton → project name). See
[Get Started](get-started.md).

## How do I add a new skeleton?

Create `templates/<name>/` with a `skeleton.meta` descriptor, add a scaffold script under
`bin/scaffold/`, and the menu discovers it automatically. See [Contributing](contributing.md).

## Online vs offline scaffolds — what's the difference?

If you connect a GitHub remote, the scaffold ships GitHub-only assets (Actions workflows,
CODEOWNERS, PR template). Without one, it ships an offline git-diff workflow instead. Library
projects also switch versioning: online = tag-driven, offline = a local `poe bump_version`
(`cz bump`, run inside the generated project — not a BlueprintX `make` target).

## I don't use a PR review bot — will the generated project's required check ever pass?

The scaffolder asks *"Do you have (or will you install) a PR review bot such as CodeRabbit
on this repo?"*. Answer **no** and it skips copying `.review-bots.yaml` instead of shipping
it empty — `reviewers: []` is treated by the gate as "switched off from inside the very PR
it polices" and raises, which is worse than never having adopted the gate at all. With the
file absent, `check_review_threads.py` reads "the review-thread gate is not adopted here"
and exits 0: the required check still runs on every PR (nothing else changes in `.github/`),
it just reports success instead of demanding a reviewer that will never exist. Answer **yes**
later and re-adding the roster turns the gate back on — at the path the gate reads, which differs
by language: for Python copy `templates/python-common/.review-bots.yaml` to the project root; for
TypeScript copy `templates/ts-common/.github/.review-bots.yaml` to `.github/.review-bots.yaml`. See blueprintx#374 (why this needed
a fix) and blueprintx#262 (why an empty roster is not the opt-out).

## How does a scaffolded repo close the issue a merged PR delivered?

Every GitHub-connected scaffold ships `.github/workflows/close-linked-issues.yml` (blueprintx#604).
GitHub's own `Closes #N` linking can come back empty (a non-default base branch, a `Closes: #N`
with a colon, a bot-performed merge), which leaves the issue open and keeps a Projects "Item closed"
-> Done automation from firing. On a merged same-repo PR the workflow closes:

- the issue number in the branch name, `<type>/<N>-<slug>` first, with a trailing `-N` as the
  fallback only when that form is absent (`feat/12-add-thing` closes issue 12, `fix/thing-25`
  closes issue 25);
- every `#N` after `Closes`, `Fixes` or `Resolves` in the PR body (colon allowed).

It deliberately skips `dependabot/*` and `renovate/*` branches (a trailing `-4` there is a version,
not an issue), the PR's own number, any number that is a PR, and `owner/repo#N` references, which
point at another repository. A fork PR is skipped too: its token is read-only. The branch name and
PR body are untrusted text and reach the script only through `env:`. It complements, and does not
replace, the Projects "Item closed -> Done" workflow. It is dropped with the rest of `.github/` in
offline mode.

## How is BlueprintX itself versioned?

The version is the git tag. Cut a release from the **Release** GitHub Action (enter the version
once); `blueprintx --version` resolves it via `git describe` from a checkout, or a stamped
literal for a packaged install. See the [Changelog](changelog.md).

## Which install methods are supported?

Homebrew, Chocolatey, Snap, apt, and `make install` from a clone — see the project README.
