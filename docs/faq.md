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

BlueprintX carries `close-linked-issues.yml` and its `bin/close_linked_issues.sh` under
`templates/common/` (blueprintx#604), but generated projects do not receive them yet: the scaffold
scripts do not copy them until the wiring step tracked in
[#604](https://github.com/guilhermegor/blueprintx/issues/604) lands. Once wired, it behaves as
follows.

GitHub's own `Closes #N` linking can come back empty (a `Closes: #N` with a colon, or a merge
that did not link), which leaves the issue open and keeps a Projects "Item closed" -> Done
automation from firing. On a merged same-repo PR **into the default branch** the workflow closes,
matching strictly (a wrong closure is worse than a missed one). A PR merged into another branch (a
stacked PR) closes nothing, because the work has not reached the default branch. Merges made with
the default `GITHUB_TOKEN` (an auto-merge or merge-queue action) never trigger
`pull_request: closed`, so only merges by a person, an App token or a PAT are covered:

- the issue number in a branch named `<type>/<N>-<slug>`, where the type is `feat`, `feature`,
  `fix`, `bugfix`, `hotfix`, `docs`, `refactor`, `chore` or `test` and `N` is not a year-month date
  (`feat/12-add-thing` closes issue 12; `feat/1999-x` closes 1999; `chore/2026-10-cleanup` and `fix/python-3-12` close
  nothing, and a trailing `-N` is never read);
- each `Closes #N`, `Fixes #N` or `Resolves #N` pair in the PR body (GitHub's closing keywords
  `close`, `fix` and `resolve` in their `-s`/`-d`/`-es` forms; colon allowed), at a word boundary. `Closes #1, #2` closes
  only `#1`, and a negated use such as "does not fully fix #12" (up to three words after the
  negation) is ignored.

It skips the whole PR, branch and body alike, for `dependabot/*`, `renovate/*` and `release/*`
branches (their bodies quote upstream `Fixes #N` text, and a trailing `-4` is a version). It also
skips the PR's own number, any number that is a PR, and `owner/repo#N` references, which point at
another repository. A fork PR is skipped too: its token is read-only. A missing issue (HTTP 404, or 410 for a deleted issue or a repo with Issues
disabled) is skipped; any other API error fails the job, and one failed close does not stop the others. The
branch name and PR body are untrusted text and reach the script only through `env:`. It
complements, and does not replace, the Projects "Item closed -> Done" workflow. It is dropped with
the rest of `.github/` in offline mode.

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
comment is a review when it has one of these shapes. A roster issue comment counts only with the
ladder attribution line or a CodeRabbit header, so a status notice such as `Review ladder: all
rungs failed` is not a review. A printed count wins over everything else:

- CodeRabbit's body sections `Outside diff range comments (N)` and `Duplicate comments (N)`
  with `N > 0`: these live only in the body, so they need a reply even when `Actionable comments
  posted: 0`;
- `Actionable comments posted: N` alone: the N findings are inline threads, which the thread
  check already holds (reply and resolve), so the body needs no extra reply for them;
- `N finding(s) across M reviewed file(s)` at the start of a line (the ladder posts no
  threads): `0` is clean, `N > 0` needs a reply;
- the ladder attribution line `Fallback review — runtime: <x>, model: <y> (selected by: <z>)`
  without a count (the claude rung writes prose): a review, unless the prose is only
  `No findings.`;
- a `Review` or `Findings` heading, bullet, bold label or `Review:` line, and numbered
  `Finding 1:` items;
- a severity emoji, `Major`/`Critical`/`Minor`/`Blocker` opening a line as bold, in brackets or
  before `:`/a dash, `Severity: <word>`, or a count that opens a line (`2 finding(s)`).

A line that is only `No findings.`, `Review: no findings`, `Minor: none` or `None.` (and a
heading directly followed by one) is clean. Nitpick and Trivial lines never need a reply.
CodeRabbit's walkthrough, rate-limit and command-reply comments are not reviews because of their
SHAPE: they carry no ladder attribution line, `Actionable` header or body section, and a roster
issue comment counts as a review only with one of those.

Count authority binds to the author, not the body: the `Actionable` header only speaks for
CodeRabbit, and the `N finding(s) across` count only for the ladder app and only with its
attribution line. Any other author's counts are ignored and its body is read by structure, so
quoting a header never clears findings. Quoted lines and fenced blocks are ignored too.

Missing or unrecognised input fails closed: a body section with no parsable count, a ladder
attribution with nothing after it, and a review comment with no timestamp all count as findings;
only an explicit clean statement or a stated `0` clears a review. Issue comments, reviews and
threads are all paginated, so a PR with 140 comments is read in full; a page that fails to load
fails the check instead of shortening the list.

### How the gate classifies an answer

An answer comes from outside the reviewer roster, is a user account (not a bot, app, organization or deleted ghost),
and is posted **after** the review. It counts when it is either 100 characters or longer, or
has an answer shape at any length: a line that opens with `Reply to review <id>`,
`Answer(s) to ... review`, `Re: review`, `Verdicts`/`Judgment on the ... review`, or a
`review <id>` citation,
`Addressed in <sha>`/`Fixed in <sha>`, a `Finding N:` heading, or a `> quoted finding`
followed by a response. A review request (`@coderabbitai re-review`, `Ready for re-review`) or a status line (`Not
answered yet`) is neither. One reply after the latest
review answers the earlier ones; a body has no thread, so nothing needs resolving. When threads
are also open, the failure lists both. Re-run the check after replying. The tests in
`test_review_threads_gate.py` list every shape with a witness that fails without its marker.
The rule is weaker than a thread: a long comment answers without being tied to a finding.

## Which install methods are supported?

Homebrew, Chocolatey, Snap, apt, and `make install` from a clone — see the project README.
