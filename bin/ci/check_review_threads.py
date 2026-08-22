"""Fail a PR whose review threads are not FINISHED — answered AND resolved.

A finding takes two actions and this gate requires both:

1. **Reply** on the thread with what changed and why.
2. **Resolve** the conversation once that reply is posted.

A review finding is dealt with in **two** halves — change the code, and **reply on the thread**
— and only the first is visible from the editor. The second is what a future session reads: a
thread holding just "finding" plus "addressed in commit <sha>" records that something changed,
never *why* — that the finding was deeper than reported, that the fix was relocated rather than
applied, that a sibling case was deliberately left alone. That rationale is the asset.

⚠️ ``isResolved`` does **not** answer this. A good review bot closes its own thread the moment
it sees the fix, so the flag measures the BOT's satisfaction, not the author's response.
Measured on the PR that motivated this gate: all 14 threads showed ``isResolved: true`` and
**11 of them held no reply from the author at all**.

The predicate is therefore about **thread content, never resolver identity**:

    a thread is answered when it holds at least one comment from an author OUTSIDE the
    declared review-bot roster, of at least ``int_min_chars`` characters.

That single rule settles three questions at once — what counts as answered (a bot's own
acknowledgement does not), who may resolve (anyone; identity is not the signal), and
bot-replying-to-bot (excluded by construction). Two rules people reach for first —
*"only a human may resolve"* and *"the last comment must be human"* — **fail the best case**,
because a good bot acknowledges the human's reply and then resolves, so the bot's comment is
always last.

**Provider-agnostic by construction.** The roster is data in ``.review-bots.yaml``; no tool is
named in the logic here. Adding a reviewer is adding a row. Note the shapes genuinely differ:
one tool posts inline threads, another posts only a status check and no thread at all — a
roster that assumes "every reviewer speaks in threads" is born broken, which is why an empty
thread list is not a THREAD failure.

⚠️ It is not a pass either, and this paragraph used to say it was. An empty thread list is what
you get both when a reviewer ran and found nothing AND when no reviewer ever ran — opposite
facts, one number. Reading threads alone the gate reported the second as success, and PRs #204
and #213 merged unreviewed with every check green. :func:`find_missing_review_problem` owns that
question separately, keyed on a SUBMITTED REVIEW rather than on threads, so the two outcomes can
print different sentences.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys


try:
	import yaml
except ModuleNotFoundError:  # pragma: no cover - the gate self-skips without its parser
	yaml = None  # type: ignore[assignment]


_ROSTER_FILE = ".review-bots.yaml"

# ⚠️ GraphQL and REST disagree on a bot's login, and the gate lives or dies on it.
#
# REST reports `coderabbitai[bot]`; the GraphQL `author { login }` field returns the Bot
# actor's login WITHOUT the suffix — `coderabbitai`. The roster is written in the REST form
# (that is the login GitHub shows everywhere else), so a literal comparison against GraphQL
# output NEVER MATCHED. Every reviewer comment therefore counted as an "answer", and the gate
# reported "all threads answered" on a PR where nobody had replied to anything.
#
# It is the worst possible failure for a gate: permanently, silently green. Both sides are now
# normalised, and `test_review_threads_gate.py` pins the bot-suffix case by name.
_BOT_SUFFIX = "[bot]"


def normalise_login(str_login: str) -> str:
	"""Return a login comparable across GitHub's REST and GraphQL spellings.

	Parameters
	----------
	str_login : str
	    A login as either API reports it, e.g. ``coderabbitai[bot]`` or ``coderabbitai``.

	Returns
	-------
	str
	    The login without a trailing ``[bot]`` suffix, so the two spellings compare equal.
	"""
	str_clean = (str_login or "").strip()
	return str_clean[: -len(_BOT_SUFFIX)] if str_clean.endswith(_BOT_SUFFIX) else str_clean
# Floor for a "substantive" reply. Measured, not invented: the replies on the PR that motivated
# this gate ran 100-667 characters (median 439), and an earlier sample of genuine verdict
# replies ran 356-1126. 100 sits at or below the shortest real one, so it excludes "done" and
# "fixed" without ever arguing with a real answer.
_MIN_REPLY_CHARS = 100

# ⚠️ `reviews` is here because THREADS ALONE CANNOT SEE AN ABSENT REVIEWER.
#
# A reviewer that ran and found nothing produces zero threads. A reviewer that never ran
# produces zero threads. Reading only `reviewThreads`, those are the same number, and the
# gate reported the second as success — see `find_missing_review_problem`.
#
# A submitted review is the discriminator, and it had to be measured rather than assumed:
# on #204 and #213 (both merged unreviewed) the roster posted an issue COMMENT — the
# star-gate refusal notice — but `reviews` was 0. So "the roster said something" would have
# passed both; "the roster submitted a review" fails both and passes #209 (10) and #215 (1).
# ⚠️ THE `states:` FILTER ON `reviews` IS LOAD-BEARING — measured, not defensive. Without it the
# connection also returns unsubmitted DRAFT reviews. Verified on #216: opening a draft review and
# re-querying showed it in the connection. The gate would then read "a reviewer reported" off
# something nobody else can see — the vacuous pass this whole check exists to remove. It lives
# outside the query string on purpose: a comment inside it is shipped over the wire on every
# call, and its wording would collide with the test that pins the filter. Raised by review on #216.
# ⚠️ BOTH CONNECTIONS PAGINATE, AND THE THREADS HALF IS THE DANGEROUS ONE.
#
# `first:100` is a CAP, not "all". Raised by review on #216 for `reviews`, where truncation
# causes a false FAILURE — annoying, and it needs 100 non-roster reviews before the roster's
# first (measured: `first` returns OLDEST first, `last` returns newest). The same cap on
# `reviewThreads` is worse and nobody flagged it: thread 101 is simply never examined, and the
# gate prints "All 100 review thread(s) answered" over unfinished conversations — a false PASS,
# which is the exact shape this file exists to eliminate.
_QUERY = """
query($owner:String!, $repo:String!, $number:Int!, $rc:String, $tc:String) {
  repository(owner:$owner, name:$repo) {
    pullRequest(number:$number) {
      author { login }
      reviews(
        first:100, after:$rc,
        states:[APPROVED, CHANGES_REQUESTED, COMMENTED, DISMISSED]
      ) {
        pageInfo { hasNextPage endCursor }
        nodes { author { login } }
      }
      reviewThreads(first:100, after:$tc) {
        pageInfo { hasNextPage endCursor }
        nodes {
          isResolved
          isOutdated
          path
          comments(first:50) { nodes { author { login } body } }
        }
      }
    }
  }
}
"""


def _roster_exists_on_default_branch(path_root: pathlib.Path) -> bool:
	"""Return whether the roster file is present on the repository's default branch.

	Returns
	-------
	bool
		``True`` only when git can prove the file exists there. Any failure (no git, shallow
		clone, no remote) returns ``False``, so an unresolvable state never invents a violation.
	"""
	for str_ref in ("origin/HEAD", "origin/main", "origin/master"):
		cls_run = subprocess.run(  # noqa: S603
			["git", "-C", str(path_root), "cat-file", "-e", f"{str_ref}:{_ROSTER_FILE}"],
			capture_output=True,
			check=False,
		)
		if cls_run.returncode == 0:
			return True
	return False


def load_roster(path_root: pathlib.Path) -> set[str]:
	"""Read the declared review-bot logins.

	Parameters
	----------
	path_root : pathlib.Path
	    Repository root holding ``.review-bots.yaml``.

	Returns
	-------
	set of str
	    Logins treated as reviewers rather than as answers. Empty when the file is absent,
	    which makes the gate a no-op rather than a source of false failures.
	"""
	path_roster = path_root / _ROSTER_FILE
	if yaml is None:
		return set()
	if not path_roster.is_file():
		# ⚠️ ABSENT is only "not adopted here" when it was never there. If the DEFAULT branch
		# carries the roster and this branch does not, the file was DELETED — and since an
		# empty roster makes the gate a no-op, deleting it is a one-line way to switch the
		# gate off inside the very PR it is meant to police. Fail loudly instead.
		if _roster_exists_on_default_branch(path_root):
			raise RuntimeError(
				f"{_ROSTER_FILE} exists on the default branch but not here — deleting it "
				f"disables this gate. Restore it, or remove it on the default branch first."
			)
		return set()
	dict_roster = yaml.safe_load(path_roster.read_text(encoding="utf-8")) or {}
	return {
		normalise_login(str(d.get("login", "")))
		for d in (dict_roster.get("reviewers") or [])
		if d.get("login")
	}


def _fetch_page(
	str_owner: str,
	str_repo: str,
	int_number: int,
	str_review_cursor: str | None,
	str_thread_cursor: str | None,
) -> dict:
	"""Run one page of the query.

	Returns
	-------
	dict
	    The ``pullRequest`` node for this page.

	Raises
	------
	RuntimeError
	    If the API call fails, so an unreachable API is never mistaken for a clean PR.
	"""
	list_cmd = [
		"gh",
		"api",
		"graphql",
		"-f",
		f"query={_QUERY}",
		"-F",
		f"owner={str_owner}",
		"-F",
		f"repo={str_repo}",
		"-F",
		f"number={int_number}",
		"-F",
		f"rc={str_review_cursor}" if str_review_cursor else "rc=",
		"-F",
		f"tc={str_thread_cursor}" if str_thread_cursor else "tc=",
	]
	# Constant argv built from CI-provided identifiers; no shell is involved.
	cls_run = subprocess.run(list_cmd, capture_output=True, text=True, check=False)  # noqa: S603
	if cls_run.returncode != 0:
		raise RuntimeError(f"GraphQL query failed: {cls_run.stderr.strip()[:400]}")
	dict_out = json.loads(cls_run.stdout)
	if "errors" in dict_out:
		raise RuntimeError(f"GraphQL returned errors: {dict_out['errors']}")
	return dict_out["data"]["repository"]["pullRequest"]


def fetch_pull_request(str_owner: str, str_repo: str, int_number: int) -> dict:
	"""Fetch the PR's author, submitted reviews and review threads in one GraphQL call.

	Parameters
	----------
	str_owner : str
	    Repository owner.
	str_repo : str
	    Repository name.
	int_number : int
	    Pull-request number.

	Returns
	-------
	dict
	    The ``pullRequest`` node, carrying ``author``, ``reviews`` and ``reviewThreads``.

	Raises
	------
	RuntimeError
	    If the API call fails, so an unreachable API is never mistaken for a clean PR.
	"""
	dict_pr = _fetch_page(str_owner, str_repo, int_number, None, None)
	dict_reviews = dict_pr["reviews"]
	dict_threads = dict_pr["reviewThreads"]

	# Follow both cursors until neither has a next page. Independent cursors, one request each
	# round: passing a cursor for a connection that is already exhausted just re-returns its
	# last (empty) page, so the loop terminates on the slower of the two.
	while dict_reviews["pageInfo"]["hasNextPage"] or dict_threads["pageInfo"]["hasNextPage"]:
		dict_next = _fetch_page(
			str_owner,
			str_repo,
			int_number,
			dict_reviews["pageInfo"]["endCursor"] if dict_reviews["pageInfo"]["hasNextPage"] else None,
			dict_threads["pageInfo"]["endCursor"] if dict_threads["pageInfo"]["hasNextPage"] else None,
		)
		for dict_side, str_key in ((dict_reviews, "reviews"), (dict_threads, "reviewThreads")):
			if not dict_side["pageInfo"]["hasNextPage"]:
				continue
			dict_side["nodes"].extend(dict_next[str_key]["nodes"])
			dict_side["pageInfo"] = dict_next[str_key]["pageInfo"]
	return dict_pr


def find_missing_review_problem(
	list_reviews: list[dict],
	set_roster: set[str],
	str_pr_author: str = "",
) -> str | None:
	"""Return a problem when no declared reviewer ever reported on this PR.

	Parameters
	----------
	list_reviews : list of dict
	    Submitted reviews, each with an ``author`` node.
	set_roster : set of str
	    Logins of the declared reviewers.
	str_pr_author : str, optional
	    Login of the PR author; a roster member's own PR is exempt.

	Returns
	-------
	str or None
	    A human-readable problem, or ``None`` when at least one reviewer reported.
	"""
	set_roster = {normalise_login(s) for s in set_roster}
	if normalise_login(str_pr_author) in set_roster:
		# A reviewer's own PR (a bot's dependency bump). Requiring it to review itself is a
		# gate nobody can satisfy, and those get bypassed with --admin, taking the real
		# blocks with them.
		return None

	set_reported = {
		normalise_login((d.get("author") or {}).get("login") or "") for d in list_reviews
	} & set_roster
	if set_reported:
		return None

	return (
		f"no declared reviewer ever reported on this PR — expected one of "
		f"{', '.join(sorted(set_roster))} to submit a review, and none did. "
		"This is NOT 'the reviewer found nothing': a reviewer that ran and found nothing "
		"still submits a review, so zero threads would be fine. Zero REVIEWS means the "
		"reviewer never ran, and nothing on this PR has been looked at.\n"
		"Trigger it (a comment such as '@coderabbitai review' from a user account, which "
		"is what .github/workflows/coderabbit_trigger.yml automates) and re-run this check."
	)


def find_thread_problems(
	list_threads: list[dict],
	set_roster: set[str],
	int_min_chars: int = _MIN_REPLY_CHARS,
	*,
	bool_require_resolved: bool = True,
) -> list[str]:
	"""Return one problem per thread that nobody outside the roster answered.

	Parameters
	----------
	list_threads : list of dict
	    Review threads as returned by :func:`fetch_threads`.
	set_roster : set of str
	    Logins that count as reviewers rather than as answers.
	int_min_chars : int, optional
	    Minimum length for a reply to count as substantive.
	bool_require_resolved : bool, keyword-only, optional
	    Whether an answered-but-open thread is a problem. ⚠️ CI passes ``False``: see
	    ``main`` for why a job that cannot re-evaluate a condition must not assert it.

	Returns
	-------
	list of str
	    Human-readable problems; empty when every thread carries an answer.
	"""
	# Normalise the roster here too, so the predicate is correct however the caller built the
	# set — `load_roster` already normalises, but a hand-built set (a test, another caller)
	# would otherwise silently never match, which is the exact defect this function had.
	set_roster = {normalise_login(s) for s in set_roster}

	list_problems: list[str] = []
	for dict_thread in list_threads:
		list_comments = dict_thread["comments"]["nodes"]
		if not list_comments:
			continue
		list_answers = [
			c
			for c in list_comments
			if normalise_login((c.get("author") or {}).get("login") or "") not in set_roster
			and len((c.get("body") or "").strip()) >= int_min_chars
		]
		str_first = (list_comments[0].get("body") or "").strip().splitlines()
		str_title = next(
			(s for s in str_first if s.startswith("**")),
			str_first[0] if str_first else "",
		).strip("* ")[:90]
		str_path = dict_thread.get("path", "?")

		if not list_answers:
			str_state = "resolved" if dict_thread.get("isResolved") else "open"
			list_problems.append(
				f"{str_path}: thread is {str_state} but nobody outside the "
				f"reviewer roster answered it — {str_title}"
			)
			continue

		# ANSWERED but still OPEN. Both halves are required: the reply records the reasoning,
		# and resolving records that the exchange is finished. Without this second check a PR
		# merges with live threads nobody ever closed — measured on PR #180, where two threads
		# arrived after the last gate run and shipped open and unanswered, because GitHub's
		# `required_conversation_resolution` was off and nothing else looked.
		if bool_require_resolved and not dict_thread.get("isResolved"):
			list_problems.append(
				f"{str_path}: thread is answered but NOT resolved — resolve the conversation "
				f"once the reply is posted — {str_title}"
			)
	return list_problems


def report_verdict(
	list_problems: list[str],
	int_threads: int,
	bool_require_resolved: bool,
) -> int:
	"""Print the verdict and return the exit code.

	Parameters
	----------
	list_problems : list of str
	    Problems from :func:`find_thread_problems`.
	int_threads : int
	    How many review threads were examined.
	bool_require_resolved : bool
	    Whether the resolve half was asserted, so the wording matches what was checked.

	Returns
	-------
	int
	    ``1`` when there are problems, ``0`` otherwise.
	"""
	for str_problem in list_problems:
		print(f"❌ {str_problem}")
	if list_problems:
		print(
			f"\n{len(list_problems)} of {int_threads} review thread(s) are not finished.\n"
			"A finding takes BOTH halves: REPLY with what changed and why, then RESOLVE the "
			"conversation.\n"
			"- Resolving without replying is not answering: a reviewer bot closes its own threads "
			"when it sees the fix, so the resolved flag records ITS satisfaction, never your "
			"reasoning — and that reasoning is what the next session reads.\n"
			"- Replying without resolving leaves the thread live, so nothing distinguishes a "
			"finished exchange from one still in progress, and the PR can merge with it open."
		)
		return 1
	if not int_threads:
		# Reached only once a reviewer HAS reported — find_missing_review_problem owns the
		# other case, and the two must never print the same sentence again.
		print("A declared reviewer reported and raised no findings (0 review threads).")
		return 0
	str_scope = "answered and resolved" if bool_require_resolved else "answered"
	print(f"All {int_threads} review thread(s) {str_scope}.")
	return 0


def main() -> int:
	"""Check the current PR's review threads.

	Returns
	-------
	int
	    ``0`` when every thread is answered (or the repo declares no roster), ``1`` otherwise.
	"""
	str_repo_full = os.environ.get("GITHUB_REPOSITORY", "")
	str_number = os.environ.get("PR_NUMBER", "")
	if not str_repo_full or not str_number.isdigit():
		print("PR_NUMBER / GITHUB_REPOSITORY not set — nothing to check")
		return 0

	path_root = pathlib.Path.cwd()
	set_roster = load_roster(path_root)
	if not set_roster:
		print(f"No {_ROSTER_FILE} — the review-thread gate is not adopted here")
		return 0

	str_owner, _, str_repo = str_repo_full.partition("/")
	dict_pr = fetch_pull_request(str_owner, str_repo, int(str_number))
	list_threads = dict_pr["reviewThreads"]["nodes"]

	# ⚠️ THE EMPTY SET IS THE CASE THIS GATE MOST NEEDS TO CATCH, AND IT USED TO PASS IT.
	#
	# With zero threads the loop below finds zero problems and the gate printed
	# "All 0 review thread(s) answered." — green. So the check that exists to stop a PR
	# merging with unfinished review conversations could not stop one merging with NO REVIEW
	# AT ALL, the only case where nothing else is watching. Measured on #204: 29 of 30 checks
	# passed and it merged with the reviewer having posted only its refusal notice.
	str_missing = find_missing_review_problem(
		dict_pr.get("reviews", {}).get("nodes", []),
		set_roster,
		(dict_pr.get("author") or {}).get("login") or "",
	)
	if str_missing:
		print(f"❌ {str_missing}")
		return 1
	# ⚠️ A JOB MUST NOT ASSERT WHAT IT CANNOT RE-EVALUATE.
	#
	# Resolving a thread emits `pull_request_review_thread`, which is NOT a workflow trigger,
	# so nothing re-runs this after a resolve. Asserting the resolve half here produces a run
	# that is red FOREVER on a PR that is actually finished — measured: 7 stale red runs on one
	# PR, every one of them from a moment that had already passed.
	#
	# A check that is red-by-design after you did the right thing is the fastest way to teach
	# people that red does not mean anything. So CI asserts only the REPLY half, which a review
	# comment genuinely does re-trigger. The resolve half is enforced where it CAN be evaluated
	# live: the `required_conversation_resolution` ruleset at the merge button, and the local
	# pre-merge / Stop hooks. Set REVIEW_THREADS_REQUIRE_RESOLVED=1 to assert both (the local
	# default, since a local run is always current).
	bool_require_resolved = os.environ.get("REVIEW_THREADS_REQUIRE_RESOLVED", "1") == "1"
	list_problems = find_thread_problems(
		list_threads, set_roster, bool_require_resolved=bool_require_resolved
	)

	return report_verdict(list_problems, len(list_threads), bool_require_resolved)


if __name__ == "__main__":
	# Windows' stdout defaults to cp1252, which cannot encode the status glyphs this
	# script prints: it would die with UnicodeEncodeError before reporting anything. And
	# because this backs an always_run pre-commit hook, that crash blocks EVERY commit from
	# a Windows checkout rather than failing the file under check. Fixed at the I/O seam so
	# the glyphs stay; a test pins it with PYTHONIOENCODING=cp1252.
	for cls_stream in (sys.stdout, sys.stderr):
		if hasattr(cls_stream, "reconfigure"):
			cls_stream.reconfigure(encoding="utf-8", errors="replace")

	sys.exit(main())
