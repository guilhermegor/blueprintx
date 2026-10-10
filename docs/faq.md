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

### When does a review still count after the branch moves?

A review is pinned to the commit it was written against. When no review names the head, the
gate asks whether the PR's **own patch** changed between the reviewed commit `R` and the head
`H`. If it did not, the review covers `H` and the gate prints
`review at R still covers H: the head only merges the base, the PR's own patch is unchanged`.
That is the case of `update-branch` under the strict-serial ruleset: main is merged in, no code
is written, and a second review of the same diff would only spend a reviewer rung.

The patch is the diff from the merge base with the base branch to the commit. It is
fingerprinted as the compare API reports it, with only the hunk coordinates
(`@@ -a,b +c,d @@`) removed. Everything else is kept: the function context after the closing
`@@`, the context lines, and all whitespace. This is stricter than `git patch-id --stable`,
which also drops the function context and normalises whitespace. The CI checkout is shallow
(`actions/checkout` defaults to `fetch-depth: 1`), so there is no local history for
`git merge-base`; the gate reads the same diff from the GitHub compare API
(`compare/<base>...<commit>`), which computes the merge base server side.

Both compares name the base by the commit SHA read once with the PR, never by branch name, so a
retarget or a push to the base between the two reads cannot make them measure different bases.
Each commit is fingerprinted once, however many reviewed commits are compared with the head.

What carries forward is therefore narrower than "any update-branch". A base edit that only
shifts the PR's hunks (lines added above or below them) leaves the fingerprint alone. A
conflict-free base edit inside a hunk's three context lines changes the context, so the review
goes stale; that fails safe. The tests pin both cases against real `git diff` output. Known
ceiling: an identical edit moved within one function, between identical context lines, still
matches, as it does for `git patch-id`.

Still superseded, so a new review is needed: a merge that resolves a conflict, any new commit,
and a force-push that rewrites the code, because each changes the fingerprint. The gate fails
closed: a missing commit, an API error, a malformed response, a binary or oversized file with
no patch text, or a full 300-file list is read as "not covered". The compare API returns at most
300 files whatever `per_page` says (it pages commits, not files), so a list that long may be cut
off. The gate asks for `per_page=1` to keep the commit list, which it does not use, small.

## Which install methods are supported?

Homebrew, Chocolatey, Snap, apt, and `make install` from a clone — see the project README.
