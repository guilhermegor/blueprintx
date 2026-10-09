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

## How is BlueprintX itself versioned?

The version is the git tag. Cut a release from the **Release** GitHub Action (enter the version
once); `blueprintx --version` resolves it via `git describe` from a checkout, or a stamped
literal for a packaged install. See the [Changelog](changelog.md).

## Does a review that only has a body need an answer?

Yes. A roster reviewer that posts findings as the review **body**, with no inline thread, used
to satisfy `Review threads answered` unread, because the gate only counted threads (16 PRs
merged that way on 2026-10-05, blueprintx#630). Now a roster review (on any commit, as threads
are; a `DISMISSED` one is skipped) whose body has one of these shapes needs a reply:

- a severity emoji (red, orange or yellow circle);
- `Major`, `Critical`, `Minor` or `Blocker` as bold (`**Major**`) or in brackets at the START of
  a line, or at the start of a line before `:`, a dash or an em dash;
- `Severity: <word>`, or a count that opens a line (`2 finding(s)`, `Found 2 findings`);
- a `Findings`, `Issues` or `Problems` heading.

Nitpick and Trivial lines (CodeRabbit's `Nitpick` and `Trivial` markers) never need a reply:
they are optional, and requiring one would re-red the gate on most CodeRabbit reviews. Prose
such as "a *minor* cleanup" or "Addressed 2 findings" is not matched. A line that is only
`No findings.`, `No blocking bugs found.`, `Minor: none`, `Severity: n/a` or `None.` (and a
findings heading directly followed by one) is clean; the same words inside a longer sentence
are not. The tests in `test_review_threads_gate.py` list every shape. Be aware the rule is
weaker than a thread: ANY 100-character comment from a human account, posted after the review,
answers every earlier body, and nothing ties it to a finding. A deleted (ghost) author or a
bot never counts. The reply is a PR comment, posted **after** the review; one reply after the latest
findings body answers the earlier ones. A body has no thread, so nothing needs resolving. When
threads are also open, the failure lists both. Re-run the check after replying.

## Which install methods are supported?

Homebrew, Chocolatey, Snap, apt, and `make install` from a clone — see the project README.
