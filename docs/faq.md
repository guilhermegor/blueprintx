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
merged that way on 2026-10-05, blueprintx#630). The gate does not parse prose to guess; it
classifies a comment by the structure the comment declares for itself, and when that is
ambiguous it counts the comment as a review, so a valid review is never dropped.

### How the gate classifies a review

A roster author's review (on any commit, as threads are; a `DISMISSED` one is skipped) or issue
comment (some ladder rungs post that way) is a review when it has one of these shapes. A
printed count wins over everything else:

- `Actionable comments posted: N` (CodeRabbit): `0` is clean, `N > 0` needs a reply, whatever
  the rest of the body says;
- `N finding(s) across M reviewed file(s)` (the ladder): same rule;
- the ladder attribution line `Fallback review — runtime: <x>, model: <y> (selected by: <z>)`
  without a count (the claude rung writes prose): a review, unless the prose is only
  `No findings.`;
- a `Review` or `Findings` heading, bullet, bold label or `Review:` line, and numbered
  `Finding 1:` items;
- a severity emoji, `Major`/`Critical`/`Minor`/`Blocker` opening a line as bold, in brackets or
  before `:`/a dash, `Severity: <word>`, or a count that opens a line (`2 finding(s)`).

A line that is only `No findings.`, `Review: no findings`, `Minor: none` or `None.` (and a
heading directly followed by one) is clean. Nitpick and Trivial lines never need a reply.
CodeRabbit's walkthrough, rate-limit and command-reply comments carry an auto-generated marker
and are not reviews.

### How the gate classifies an answer

An answer comes from outside the reviewer roster, is not a bot or a deleted (ghost) account,
and is posted **after** the review. It counts when it is either 100 characters or longer, or
has an answer shape at any length: `Reply to review <id>`, `Answer(s) to ... review`,
`Re: review`, `Verdicts`/`Judgment on the ... review`, `Review <id> verified`,
`Addressed in <sha>`/`Fixed in <sha>`, a `Finding N:` heading, or a `> quoted finding`
followed by a response. A bare `@coderabbitai review` is neither. One reply after the latest
review answers the earlier ones; a body has no thread, so nothing needs resolving. When threads
are also open, the failure lists both. Re-run the check after replying. The tests in
`test_review_threads_gate.py` list every shape with a witness that fails without its marker.
The rule is weaker than a thread: a long comment answers without being tied to a finding.

## Which install methods are supported?

Homebrew, Chocolatey, Snap, apt, and `make install` from a clone — see the project README.
