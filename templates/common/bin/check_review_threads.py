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

⚠️ A SUBMITTED REVIEW IS NOT ENOUGH EITHER — IT MUST BE A REVIEW OF **THIS** CODE.

A review is pinned to the commit it was written against and nothing re-pins it when the branch
moves, so "a roster member submitted a review" is satisfiable by code nobody looked at (#220,
measured on #219). ``find_missing_review_problem`` therefore requires a review attributed to
``headRefOid``, and prints a DIFFERENT sentence for "reviewed older code" than for "never
reviewed" — those two used to be indistinguishable, and they call for different actions.

⚠️ ``reviews == 0`` HAS SEVERAL CAUSES AND EXACTLY ONE VERDICT.

Nobody ran, the reviewer refused, it was rate-limited, or it declined as redundant — different
remedies, and the reviewer's notice is quoted so the reader can tell which. It is quoted and
never counted: every one of those outcomes carries the same "does not re-review already reviewed
commits" footnote, so the text cannot discriminate between them (#259, measured on #264 — the PR
that first tried to trust it). The failure stands in all four cases, and the message names
``@coderabbitai full review``, which unlike a plain ``review`` does not answer "already
reviewed".
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import subprocess
import sys


try:
	import yaml
except ModuleNotFoundError:  # pragma: no cover - the gate self-skips without its parser
	yaml = None  # type: ignore[assignment]


_ROSTER_FILE = ".review-bots.yaml"

# ⚠️ `posts:` IS NOT DECORATION — IT DECIDES WHO CAN SATISFY THE MISSING-REVIEW GATE.
#
# Reviewer shapes differ: some post inline review THREADS, some post only a STATUS CHECK. The
# thread half of this gate correctly subtracts BOTH (a `status` member posts no answers either),
# but `find_missing_review_problem` must consider only the members that can actually submit a
# review. Without that split, `github-actions[bot]` — which CAN submit a review with the ambient
# GITHUB_TOKEN — silently satisfies a gate whose entire purpose is "a real reviewer looked at
# this". Same class of hole as #208: a signal that reads as a review without being one.
_POSTS_THREADS = "threads"
_POSTS_STATUS = "status"
# The dict IS the branch and the frozenset IS the validity set, so the two cannot drift.
_POSTS_CAN_REVIEW = {_POSTS_THREADS: True, _POSTS_STATUS: False}
_POSTS_VALID = frozenset(_POSTS_CAN_REVIEW)

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

# ⚠️ A REVIEWER NOTICE IS QUOTED IN THE MESSAGE AND NEVER COUNTED AS A VERDICT (#259).
#
# `reviews == 0` collapses states with different remedies — nobody ran, refused, rate-limited,
# or declined as redundant — so the notice is worth SHOWING. It is not worth trusting, and the
# first draft of this file trusted it. Measured on #264, the PR that introduced it:
#
#   ✅ Action performed     "Review finished."      + the "already reviewed" footnote
#   ⚠️ Action not completed "Review rate limited."  + the "already reviewed" footnote
#   ❌ Action failed        "Review failed."        + the "already reviewed" footnote
#
# That sentence is a STANDING FOOTNOTE about how the product works, appended to every outcome —
# not a statement about this PR. Keying a pass on it made a rate-limited and an outright FAILED
# review read as "declined as redundant", which is the exact defect shape this file exists to
# remove: prose that is always true, mistaken for evidence. Caught by review on #264, which asked
# for evidence the commits were reviewed; there is none in the text, so there is no pass.
#
# ⚠️ AND THE UNSATISFIABILITY THAT JUSTIFIED THE PASS DOES NOT EXIST. #259 argued the gate would
# be unsatisfiable because the remedy it prints (`@coderabbitai review`) is the command that
# answers "already reviewed". A DIFFERENT documented command does not: `@coderabbitai full
# review` "disregards any comments that CodeRabbit has already made on this pull request, and
# generates a complete review of the entire pull request" (CodeRabbit's own docs). So the failure
# stands and the message names the command that actually clears it.
_RE_MARKUP = re.compile(r"<!--.*?-->|<[^>]+>", re.DOTALL)

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
# ⚠️ `commit { oid }` IS WHY A REVIEW COUNTS, AND IT COSTS NOTHING TO ASK FOR.
#
# A submitted review is pinned to the commit it was written against, and nothing re-pins it
# when the branch moves. Measured on #219: `head=9ae76ab` while the PR's only review was
# attributed to `9e7d1fe`, a commit superseded five minutes earlier — and the review's own
# content proved the staleness, arguing a point the newer commit had already falsified. The
# gate passed, because it asked "did a roster member submit a review?" and never "of which
# code?". Triggering a review is necessary and NOT sufficient (#220).
#
# ⚠️ `comments` HERE IS THE PR'S ISSUE-COMMENT STREAM, NOT A THREAD'S REPLIES.
#
# A reviewer that declines to work posts an ISSUE comment, never a review thread — verified on
# #257. That stream is the only place the difference between "nobody looked at this" and "these
# commits were already reviewed" is written down (#259). It is fetched `last:` rather than
# `first:` on purpose: `last` returns the NEWEST, so truncation can only drop OLD notices, and
# an old notice is the one that must not grant a pass anyway.
_QUERY = """
query($owner:String!, $repo:String!, $number:Int!, $rc:String, $tc:String) {
  repository(owner:$owner, name:$repo) {
    pullRequest(number:$number) {
      author { login }
      headRefOid
      comments(last:100) { nodes { author { login } body createdAt } }
      reviews(
        first:100, after:$rc,
        states:[APPROVED, CHANGES_REQUESTED, COMMENTED, DISMISSED]
      ) {
        pageInfo { hasNextPage endCursor }
        nodes { author { login } commit { oid } }
      }
      commits(last:1) { nodes { commit { committedDate } } }
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
		# S607 (partial path) is resolution BY DESIGN: use the `git` on PATH, the one the
		# developer's shell and CI already use, not a path hardcoded here.
		cls_run = subprocess.run(  # noqa: S603
			["git", "-C", str(path_root), "cat-file", "-e", f"{str_ref}:{_ROSTER_FILE}"],  # noqa: S607
			capture_output=True,
			check=False,
		)
		if cls_run.returncode == 0:
			return True
	return False


def posts_of(dict_row: dict) -> str:
	"""Return the ``posts:`` classification declared by one roster row.

	Parameters
	----------
	dict_row : dict
		One entry of the roster's ``reviewers:`` list.

	Returns
	-------
	str
		One of :data:`_POSTS_VALID` — ``"threads"`` or ``"status"``.

	Raises
	------
	RuntimeError
		When ``posts:`` is missing or is not one of :data:`_POSTS_VALID`. Defaulting is not
		available here in either direction: silently reading a forgotten field as ``status``
		makes the gate unsatisfiable (and unsatisfiable gates get bypassed with ``--admin``,
		taking the real blocks with them), while reading it as ``threads`` re-opens the exact
		hole this field exists to close. So the roster must say, and a row that does not is a
		configuration error the message has to name.
	"""
	str_login = str(dict_row.get("login") or "").strip()
	str_posts = str(dict_row.get("posts") or "").strip()
	if str_posts not in _POSTS_VALID:
		# Name the row AND the value it declared. A roster error that reports only "invalid
		# posts" sends the reader back through the file to work out which of N rows it meant.
		raise RuntimeError(
			f"{_ROSTER_FILE}: reviewer {str_login or '<no login>'} declares "
			f"posts: {str_posts or '<missing>'} — expected one of "
			f"{', '.join(sorted(_POSTS_VALID))}. This field decides who can satisfy the "
			f"missing-review gate, and neither default is safe, so it cannot be omitted."
		)
	return str_posts


def load_roster(path_root: pathlib.Path) -> dict[str, str]:
	"""Read the declared review-bot roster.

	Parameters
	----------
	path_root : pathlib.Path
		Repository root holding ``.review-bots.yaml``.

	Returns
	-------
	dict of str to str
		Normalised login mapped to its ``posts:`` classification. Every member counts as a
		reviewer rather than as an answer for the THREAD half; only the ``threads`` members
		can satisfy the MISSING-REVIEW half — see :func:`reviewer_logins`. Empty when the
		file was NEVER there, which makes the gate a no-op rather than a source of false
		failures.

	Raises
	------
	RuntimeError
		When the roster is absent HERE but present on the default branch — that is a
		deletion, and since an empty roster makes this gate a no-op, it would switch the
		gate off inside the very PR it is meant to police. Also propagated from
		:func:`posts_of` for a row that does not declare a usable ``posts:``.
	"""
	path_roster = path_root / _ROSTER_FILE
	if yaml is None:
		return {}
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
		return {}
	dict_yaml = yaml.safe_load(path_roster.read_text(encoding="utf-8")) or {}
	dict_roster = {
		normalise_login(str(d.get("login", ""))): posts_of(d)
		for d in (dict_yaml.get("reviewers") or [])
		if d.get("login")
	}
	if not dict_roster:
		# ⚠️ EMPTYING THE LIST IS THE SAME ONE-LINE SWITCH-OFF AS DELETING THE FILE.
		#
		# The guard above rejects a roster deleted inside the PR it polices; `reviewers: []`
		# walks through the same door with different keystrokes — the file is present, so the
		# deletion guard never fires, and `main()` reads the empty result as "not adopted here"
		# and exits 0. Opting out is documented as DELETING the file, which self-skips with a
		# message; a roster that exists and declares nobody is a disabled gate, not an absent
		# one. Raised by review on #262.
		raise RuntimeError(
			f"{_ROSTER_FILE} exists but declares no reviewers — an empty roster makes this "
			f"gate a no-op, which is the same as deleting it. Declare a reviewer, or delete "
			f"the file to opt out (that path self-skips with a message)."
		)
	return dict_roster


def reviewer_logins(dict_roster: dict[str, str]) -> set[str]:
	"""Return the roster logins that can actually submit a review.

	Parameters
	----------
	dict_roster : dict of str to str
		Roster as returned by :func:`load_roster`.

	Returns
	-------
	set of str
		The ``posts: threads`` members. A ``posts: status`` member is deliberately absent:
		it can neither be expected to review nor accepted as having reviewed.

	Raises
	------
	RuntimeError
		When a non-empty roster declares no member that can review. That roster makes the
		missing-review check unsatisfiable on every PR, and a permanently red required check
		is the fastest way to teach people that red means nothing.
	"""
	set_reviewers = {s for s, p in dict_roster.items() if _POSTS_CAN_REVIEW[p]}
	if dict_roster and not set_reviewers:
		raise RuntimeError(
			f"{_ROSTER_FILE} declares no member with posts: {_POSTS_THREADS}, so no PR can "
			f"ever satisfy the missing-review check. Declare a reviewer, or delete the "
			f"roster to opt out of this gate entirely."
		)
	return set_reviewers


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
			dict_reviews["pageInfo"]["endCursor"]
			if dict_reviews["pageInfo"]["hasNextPage"]
			else None,
			dict_threads["pageInfo"]["endCursor"]
			if dict_threads["pageInfo"]["hasNextPage"]
			else None,
		)
		for dict_side, str_key in ((dict_reviews, "reviews"), (dict_threads, "reviewThreads")):
			if not dict_side["pageInfo"]["hasNextPage"]:
				continue
			dict_side["nodes"].extend(dict_next[str_key]["nodes"])
			dict_side["pageInfo"] = dict_next[str_key]["pageInfo"]
	return dict_pr


def reviewers_who_reported(
	list_reviews: list[dict],
	set_roster: set[str],
	str_commit_oid: str = "",
) -> set[str]:
	"""Return the roster logins that submitted a review, optionally pinned to one commit.

	Parameters
	----------
	list_reviews : list of dict
		Submitted reviews, each with an ``author`` node and a ``commit`` node.
	set_roster : set of str
		Already-normalised logins that can submit a review.
	str_commit_oid : str, optional
		When given, only a review written against exactly this commit counts. When empty,
		every review counts regardless of commit — used to tell "reviewed OLDER code" apart
		from "never reviewed", which must not print the same sentence.

	Returns
	-------
	set of str
		The subset of ``set_roster`` that reported under the requested pinning.
	"""
	return {
		normalise_login((d.get("author") or {}).get("login") or "")
		for d in list_reviews
		if not str_commit_oid or ((d.get("commit") or {}).get("oid") or "") == str_commit_oid
	} & set_roster


def summarise_reviewer_notice(list_notices: list[dict], set_roster: set[str]) -> str:
	"""Return the roster's most recent notice, flattened, to quote in a failure message.

	Parameters
	----------
	list_notices : list of dict
		The PR's issue comments, oldest first — the stream a declining reviewer posts to.
	set_roster : set of str
		Already-normalised logins that can submit a review.

	Returns
	-------
	str
		The newest roster comment with markup stripped and truncated, or ``""`` when the
		roster has said nothing. ⚠️ DISPLAY ONLY, never a verdict — see the notice block
		above: every outcome carries the same "already reviewed" footnote, so the text
		cannot discriminate between them.
	"""
	# Only the NEWEST roster notice. An older one is a sentence the reviewer has since
	# superseded, so quoting it would describe a state that no longer holds.
	for dict_comment in reversed(list_notices):
		if (
			normalise_login((dict_comment.get("author") or {}).get("login") or "")
			not in set_roster
		):
			continue
		return " ".join(_RE_MARKUP.sub(" ", dict_comment.get("body") or "").split())[:200]
	return ""


def newest_roster_notice_date(list_notices: list[dict], set_roster: set[str]) -> str:
	"""Return the ``createdAt`` of the newest roster-authored notice.

	Parameters
	----------
	list_notices : list of dict
		The PR's issue comments, oldest first.
	set_roster : set of str
		Already-normalised logins that can submit a review.

	Returns
	-------
	str
		ISO-8601 timestamp, or ``""`` when the roster has said nothing. Pairs with
		:func:`summarise_reviewer_notice`, which walks the same stream for the same comment.
	"""
	for dict_comment in reversed(list_notices):
		if normalise_login((dict_comment.get("author") or {}).get("login") or "") in set_roster:
			return dict_comment.get("createdAt") or ""
	return ""


# ⚠️ TWO QUOTAS WEAR THE SAME WORDS "RATE LIMIT", AND THEY WANT OPPOSITE BEHAVIOUR (blueprintx#364).
#
# CodeRabbit emits two structurally different refusals under one umbrella phrase:
#
#   REVIEW quota — "Review rate limited." inside a `<details>` block, resets in HOURS.
#   CHAT quota   — "...exceeded the limit for the number of chat messages per hour...", resets
#                  in MINUTES — and POSTING A REVIEW REQUEST IS ITSELF A CHAT MESSAGE, so the act
#                  of asking for a review is exactly what can spend this quota.
#
# Measured on this repo, 562 notices over 7 days: 503 review, 59 chat. 10.5% is not an error rate
# a caller can round away — the NEWEST notice is what a caller reads, so one chat notice landing
# last inverts the answer. Measured 2026-08-30T18:44:28Z: a 4-minute-37-second chat wait was read
# as an hours-long review block and cost a review-request window.
#
# `NOTICE_UNKNOWN` exists because a notice that says "rate limit" in neither recognised shape is
# still NOT an all-clear — collapsing it into `NOTICE_OK` is how a caller re-derives the very
# conflation this function exists to remove.
_RE_CHAT_LIMIT = re.compile(
	r"exceeded\s+the\s+limit\s+for\s+the\s+number\s+of\s+chat\s+messages", re.IGNORECASE
)
_RE_REVIEW_LIMIT = re.compile(r"review\s+rate\s+limited", re.IGNORECASE)
_RE_ANY_RATE_LIMIT = re.compile(r"rate[\s-]?limit", re.IGNORECASE)

NOTICE_REVIEW_LIMITED = "REVIEW_LIMITED"
NOTICE_CHAT_LIMITED = "CHAT_LIMITED"
NOTICE_OK = "OK"
NOTICE_UNKNOWN = "UNKNOWN"


def classify_reviewer_notice(str_notice: str) -> str:
	"""Classify a reviewer's notice by which quota (if any) it reports.

	Parameters
	----------
	str_notice : str
		A reviewer comment body, or ``""`` when the roster has said nothing.

	Returns
	-------
	str
		One of :data:`NOTICE_CHAT_LIMITED`, :data:`NOTICE_REVIEW_LIMITED`, :data:`NOTICE_OK`
		(no rate-limit wording at all — including an empty notice), or :data:`NOTICE_UNKNOWN`
		(mentions a rate limit in neither recognised shape — see the block above).
	"""
	if _RE_CHAT_LIMIT.search(str_notice):
		return NOTICE_CHAT_LIMITED
	if _RE_REVIEW_LIMIT.search(str_notice):
		return NOTICE_REVIEW_LIMITED
	if _RE_ANY_RATE_LIMIT.search(str_notice):
		return NOTICE_UNKNOWN
	return NOTICE_OK


# 🔴 THE REVIEWER DECLARES ITS OWN WAIT — READ IT INSTEAD OF GUESSING.
#
# `retry_rate_limited_review.py` carries an earlier attempt at this idea and, measured against
# the real bodies above, matches neither format (blueprintx#364) — this is the fixed version;
# that file still needs the same fix, tracked as a follow-up rather than duplicated here.
#
# Returned in SECONDS, not minutes: the chat quota declares "N minutes AND M seconds" (a
# whole-minute unit would truncate the 37 seconds that made the #364 window wrong), while the
# review quota declares whole minutes only. Seconds is the one unit that loses nothing either way.
_RE_CHAT_WAIT = re.compile(
	r"wait\s+\*{0,2}(\d+)\s+minutes?(?:\s+and\s+(\d+)\s+seconds?)?\*{0,2}", re.IGNORECASE
)
_RE_REVIEW_WAIT = re.compile(
	r"next\s+included\s+review\s+will\s+be\s+available\s+in\s+(\d+)\s+minutes?", re.IGNORECASE
)


def parse_declared_wait(str_notice: str) -> int | None:
	"""Return the wait in SECONDS the reviewer declared, or ``None`` when it declared none.

	Parameters
	----------
	str_notice : str
		The reviewer's refusal body.

	Returns
	-------
	int or None
		Seconds to wait, or ``None`` when the notice states no parseable wait.
	"""
	cls_chat = _RE_CHAT_WAIT.search(str_notice)
	if cls_chat is not None:
		try:
			return int(cls_chat.group(1)) * 60 + int(cls_chat.group(2) or 0)
		except ValueError:
			# Untrusted external digits — mirrors the guard in the sibling parser's own file.
			return None
	cls_review = _RE_REVIEW_WAIT.search(str_notice)
	if cls_review is not None:
		try:
			return int(cls_review.group(1)) * 60
		except ValueError:
			return None
	return None


# ⚠️ COMPLETION — THE ONE NOTICE THAT IS EVIDENCE, AND WHY IT IS NOT A REVERSAL.
#
# The notice block above establishes that a roster COMMENT is not evidence a review happened,
# and that measurement stands: on #204 and #213 (both merged unreviewed) the roster posted an
# issue comment and `reviews` was 0, so "the roster said something" would have passed both.
#
# What that block rejected was the STANDING FOOTNOTE ("does not re-review already reviewed
# commits") — prose appended to every outcome, true whatever happened, therefore evidence of
# nothing. These phrases are the opposite: CodeRabbit emits them only on the path where it
# reviewed and had nothing to attach. A formal review object is produced ONLY when there are
# line comments to hang on it, so on a clean review `reviews` is 0 and threads are 0 — byte
# for byte identical to "never ran", which is the state the gate must still fail.
#
# Measured 2026-08-29, the narrow phrase against the exact counter-examples that killed the
# broad version:
#
#     #204  merged unreviewed (star-gate refusal)  reviews=0  phrase=0  -> still FAILS ✅
#     #213  merged unreviewed (star-gate refusal)  reviews=0  phrase=0  -> still FAILS ✅
#     #209  genuinely reviewed                     reviews=19 phrase=1  -> passes (already did)
#     #215  genuinely reviewed                     reviews=9  phrase=1  -> passes (already did)
#     #328  reviewed, found nothing                reviews=0  phrase=1  -> FAILED, now passes
#
# ⚠️ THIS IS A LOOSENING, NOT A PURE BUG FIX. A comment is cheaper to produce than a review
# object, so the gate proves slightly less than it did. The reduction is bounded on purpose:
# roster author only, literal vendor strings, and evidence that a review RAN — never that a
# thread was resolved. Thread strictness is untouched.
#
# ⚠️ The rate-limit notice deliberately does NOT match. "Rate limited" means the reviewer was
# turned away, which is the same as never running, and the gate must keep failing it — that
# is the difference between waiting for a review and skipping one.
_TUPLE_COMPLETION_PHRASES = (
	"review finished",
	"no actionable comments were generated",
)


def reviewer_declared_completion(
	list_notices: list[dict],
	set_roster: set[str],
	str_head_date: str = "",
) -> bool:
	"""Return whether a roster member's own notice says it reviewed THIS PR's head.

	Parameters
	----------
	list_notices : list of dict
		The PR's issue comments, oldest first — the stream the reviewer reports completion to.
	set_roster : set of str
		Already-normalised logins that can submit a review.
	str_head_date : str, optional
		ISO-8601 ``committedDate`` of the head commit. A notice created BEFORE it describes
		superseded code and is not evidence. Empty means unknown, and unknown fails closed.

	Returns
	-------
	bool
		``True`` when a roster-authored comment carries a completion phrase AND postdates the
		head commit. ⚠️ Evidence that a review HAPPENED and never that a thread was answered —
		see the COMPLETION block above.
	"""
	if not str_head_date:
		return False
	str_newest = summarise_reviewer_notice(list_notices, set_roster).casefold()
	if not any(str_phrase in str_newest for str_phrase in _TUPLE_COMPLETION_PHRASES):
		return False
	str_when = newest_roster_notice_date(list_notices, set_roster)
	# ISO-8601 UTC from GitHub sorts lexicographically, so no parsing is needed.
	return bool(str_when) and str_when >= str_head_date


# ⚠️ TWO FAILURES, TWO SENTENCES. They used to print identically, which is the whole reason
# #208 rewrote this message once already: "the reviewer ran on older code" and "no reviewer
# ever ran" call for different actions, and a reader told the wrong one wastes the trigger.
def find_missing_review_problem(
	list_reviews: list[dict],
	set_reviewers: set[str],
	str_pr_author: str = "",
	*,
	str_head_oid: str,
	list_notices: list[dict] | None = None,
	str_head_date: str = "",
) -> str | None:
	"""Return a problem when no declared reviewer ever reported on this PR's HEAD.

	Parameters
	----------
	list_reviews : list of dict
		Submitted reviews, each with an ``author`` node and a ``commit`` node.
	set_reviewers : set of str
		Logins that can actually submit a review — :func:`reviewer_logins`, NOT the whole
		roster. ⚠️ Handing this the full roster is the defect it was fixed for: a
		``posts: status`` member both gets NAMED as expected and SATISFIES the check, and
		``github-actions[bot]`` can submit a review with the ambient token.
	str_pr_author : str, optional
		Login of the PR author; a roster member's own PR is exempt.
	str_head_date : str, optional
		ISO-8601 ``committedDate`` of the head commit, so a completion notice can be pinned to
		the code it described. ⚠️ Empty fails CLOSED: unknown is not evidence.
	str_head_oid : str, keyword-only
		The PR's ``headRefOid``. ⚠️ Deliberately has NO default, like ``posts:`` on a roster
		row: an empty value silently counts every review whatever code it was written
		against, which is the vacuous pass this parameter exists to remove.
	list_notices : list of dict, optional
		The PR's issue comments, oldest first. Consulted only when nothing reviewed HEAD.

	Returns
	-------
	str or None
		A human-readable problem, or ``None`` when a reviewer reported on the head commit
		(or declared those commits already reviewed).
	"""
	set_roster = {normalise_login(s) for s in set_reviewers}
	if normalise_login(str_pr_author) in set_roster:
		# A reviewer's own PR (a bot's dependency bump). Requiring it to review itself is a
		# gate nobody can satisfy, and those get bypassed with --admin, taking the real
		# blocks with them.
		#
		# ⚠️ The exemption narrowed with the parameter, ON PURPOSE. It used to cover every
		# roster member, so a PR opened by a `posts: status` member (github-actions[bot],
		# which opens workflow PRs) skipped the check entirely — yet that author cannot
		# review, so a real reviewer CAN look at its PR and there is nothing unsatisfiable
		# about asking. The exemption is "do not ask X to review X", not "bots are exempt".
		return None

	if reviewers_who_reported(list_reviews, set_roster, str_head_oid):
		return None

	if reviewer_declared_completion(list_notices or [], set_roster, str_head_date):
		# A CLEAN review is not a missing one — see the COMPLETION block above the function.
		return None

	# The reviewer's own latest word, quoted so the reader can see WHICH zero-review state this
	# is (never ran / refused / rate-limited). Display only — see the notice block above.
	str_seen = summarise_reviewer_notice(list_notices or [], set_roster)
	str_quote = (
		f"\nThe reviewer's most recent notice on this PR reads: {str_seen}" if str_seen else ""
	)

	# TWO FAILURES, TWO SENTENCES — see the block above the function.
	if reviewers_who_reported(list_reviews, set_roster):
		return (
			f"a declared reviewer DID review this PR, but only on SUPERSEDED code — no review "
			f"is attributed to the head commit {str_head_oid[:7] or '?'}. A review is pinned to "
			"the commit it was written against and nothing re-pins it when the branch moves, so "
			"the code that would merge has not been looked at. This is NOT 'no review "
			"happened'.\n"
			"Push-triggered re-review is automatic; if it did not fire, ask for a FULL re-review "
			"(a comment such as '@coderabbitai full review' from a user account, which unlike a "
			"plain 'review' disregards what was already reviewed) and re-run this check."
			+ str_quote
		)

	return (
		f"no declared reviewer ever reported on this PR — expected one of "
		f"{', '.join(sorted(set_roster))} to submit a review, and none did. "
		"This is NOT 'the reviewer found nothing': a reviewer that ran and found nothing "
		"still submits a review, so zero threads would be fine. Zero REVIEWS means the "
		"reviewer never ran, and nothing on this PR has been looked at.\n"
		"Trigger it with '@coderabbitai full review' from a user account. ⚠️ Prefer FULL over "
		"a plain 'review': an incremental reviewer answers 'already reviewed' on commits it has "
		"seen on another PR (a reopen, a rebase, a re-PR), and a full review does not." + str_quote
	)


#
# `required_conversation_resolution` (and its ruleset spelling `required_review_thread_resolution`)
# drops a thread whose lines no longer exist in the diff. Measured on #193: the merge button was
# ENABLED over a thread reading `resolved=False outdated=True`, with every one of 29 checks green
# and the setting confirmed `enabled`. Outdating is caused by the AUTHOR'S OWN COMMIT, so it is
# precisely the state an author can manufacture — reply thinly, rewrite the commented lines,
# merge. This gate is the only layer that can assert it, which is why the message NAMES the flag
# instead of failing silently on it (#196).
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
		Review threads as returned by :func:`fetch_pull_request` (its ``reviewThreads``).
	set_roster : set of str
		Logins that count as reviewers rather than as answers.
	int_min_chars : int, optional
		Minimum length for a reply to count as substantive.
	bool_require_resolved : bool, keyword-only, optional
		Whether an answered-but-open thread is a problem. ⚠️ CI passes ``True`` — it used to
		pass ``False`` on the reasoning that a job must not assert what it cannot re-evaluate,
		which delegated the resolve half to a native setting that DROPS an outdated thread.
		See the SUPERSEDED block above ``main`` for the measurement and the accepted cost.

	Returns
	-------
	list of str
		Human-readable problems; empty when every thread carries an answer — and, when
		``bool_require_resolved`` is set, is resolved as well. Both halves are the contract:
		the reply records the reasoning, the resolution records that the exchange is over.
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

		# ANSWERED but still OPEN — see the OUTDATED block above the function.
		if bool_require_resolved and not dict_thread.get("isResolved"):
			str_why = (
				" — this thread is OUTDATED, so the merge button will NOT block on it and "
				"this check is the only thing asserting it"
				if dict_thread.get("isOutdated")
				else ""
			)
			list_problems.append(
				f"{str_path}: thread is answered but NOT resolved — resolve the conversation "
				f"once the reply is posted{str_why} — {str_title}"
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


# ⚠️ SUPERSEDED 2026-08-24 (#196). CI NOW ASSERTS BOTH HALVES, AND THE COST IS ACCEPTED.
#
# `main` used to run under REVIEW_THREADS_REQUIRE_RESOLVED=0 in CI, on the reasoning that a job
# must not assert what it cannot re-evaluate: resolving a thread emits
# `pull_request_review_thread`, which is NOT a workflow trigger, so nothing re-runs this after a
# resolve and the run sits red on a PR that is actually finished (measured: 7 stale red runs on
# one PR). That reasoning was sound; the DELEGATION it justified was not. It handed the resolve
# half to `required_conversation_resolution`, which DROPS AN OUTDATED THREAD — so the half nobody
# could re-evaluate was also the half nobody was checking, and the guarantee this file described
# was partial. A guarantee people believe in is worse than one they know is partial.
#
# The trade is therefore explicit: a resolve leaves this check RED until the run is re-run by
# hand. ⚠️ That makes the stale-run accumulation in the merge rollup (#263) load-bearing rather
# than cosmetic — the re-run is the ONLY way a finished PR goes green, so #263 must land for that
# re-run to actually clear the block.
def parse_args(list_argv: list[str] | None = None) -> argparse.Namespace:
	"""Parse this gate's CLI arguments.

	Parameters
	----------
	list_argv : list of str, optional
		Arguments to parse; ``None`` (the default) makes argparse read ``sys.argv[1:]``, so
		``sys.exit(main())`` at the bottom of this file is unaffected.

	Returns
	-------
	argparse.Namespace
		A ``json`` boolean. Every other input stays environment-only (``GITHUB_REPOSITORY``,
		``PR_NUMBER``, ``REVIEW_THREADS_REQUIRE_RESOLVED``) — unchanged by this addition.
	"""
	cls_parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
	cls_parser.add_argument(
		"--json",
		action="store_true",
		help="Emit a machine-readable JSON verdict on stdout instead of prose (default: prose).",
	)
	return cls_parser.parse_args(list_argv)


# blueprintx#364 — the gate's only interface was English prose, so every caller grepped
# sentences; one re-implementation matched the phrase "so zero threads would be fine" inside the
# no-reviewer message via `grep 'thread'` and misreported 27 PRs. `--json` is additive: the
# default (prose) path below is untouched line for line, so existing callers see no change.
def _print_skip(bool_json: bool, str_reason: str) -> int:
	"""Print a self-skip in the requested representation and return ``0``."""
	print(json.dumps({"status": "skipped", "reason": str_reason}) if bool_json else str_reason)
	return 0


def _print_missing_review(
	bool_json: bool, str_missing: str, list_notices: list[dict], set_reviewers: set[str]
) -> int:
	"""Print the missing-review failure in the requested representation and return ``1``."""
	if bool_json:
		str_notice = summarise_reviewer_notice(list_notices, set_reviewers)
		print(
			json.dumps(
				{
					"status": "fail",
					"reason": "missing_review",
					"detail": str_missing,
					"notice_classification": classify_reviewer_notice(str_notice),
				}
			)
		)
	else:
		print(f"❌ {str_missing}")
	return 1


def _print_thread_verdict(
	bool_json: bool, list_problems: list[str], int_threads: int, bool_require_resolved: bool
) -> int:
	"""Print the thread verdict in the requested representation and return the exit code."""
	if bool_json:
		print(
			json.dumps(
				{
					"status": "fail" if list_problems else "pass",
					"threads_examined": int_threads,
					"require_resolved": bool_require_resolved,
					"problems": list_problems,
				}
			)
		)
		return 1 if list_problems else 0
	return report_verdict(list_problems, int_threads, bool_require_resolved)


def main(list_argv: list[str] | None = None) -> int:
	"""Check the current PR's review threads.

	Parameters
	----------
	list_argv : list of str, optional
		CLI arguments; ``None`` defaults to ``sys.argv[1:]`` — see :func:`parse_args`.

	Returns
	-------
	int
		``0`` when every thread is answered (or the repo declares no roster), ``1`` otherwise.
	"""
	bool_json = parse_args(list_argv).json

	str_repo_full = os.environ.get("GITHUB_REPOSITORY", "")
	str_number = os.environ.get("PR_NUMBER", "")
	if not str_repo_full or not str_number.isdigit():
		return _print_skip(bool_json, "PR_NUMBER / GITHUB_REPOSITORY not set — nothing to check")

	path_root = pathlib.Path.cwd()
	dict_roster = load_roster(path_root)
	if not dict_roster:
		return _print_skip(
			bool_json, f"No {_ROSTER_FILE} — the review-thread gate is not adopted here"
		)

	# TWO sets from one roster, and they are not the same set. The thread half subtracts every
	# member (a status member posts no answers either); the missing-review half considers only
	# the members that can submit a review.
	set_roster = set(dict_roster)
	set_reviewers = reviewer_logins(dict_roster)

	str_owner, _, str_repo = str_repo_full.partition("/")
	dict_pr = fetch_pull_request(str_owner, str_repo, int(str_number))
	list_threads = dict_pr["reviewThreads"]["nodes"]
	list_notices = dict_pr.get("comments", {}).get("nodes", [])

	# ⚠️ THE EMPTY SET IS THE CASE THIS GATE MOST NEEDS TO CATCH, AND IT USED TO PASS IT.
	#
	# With zero threads the loop below finds zero problems and the gate printed
	# "All 0 review thread(s) answered." — green. So the check that exists to stop a PR
	# merging with unfinished review conversations could not stop one merging with NO REVIEW
	# AT ALL, the only case where nothing else is watching. Measured on #204: 29 of 30 checks
	# passed and it merged with the reviewer having posted only its refusal notice.
	str_missing = find_missing_review_problem(
		dict_pr.get("reviews", {}).get("nodes", []),
		set_reviewers,
		(dict_pr.get("author") or {}).get("login") or "",
		str_head_oid=dict_pr.get("headRefOid") or "",
		list_notices=list_notices,
		str_head_date=(
			((dict_pr.get("commits", {}).get("nodes") or [{}])[0].get("commit") or {}).get(
				"committedDate"
			)
			or ""
		),
	)
	if str_missing:
		return _print_missing_review(bool_json, str_missing, list_notices, set_reviewers)

	# Both halves by default; set REVIEW_THREADS_REQUIRE_RESOLVED=0 for the reply half only.
	# See the SUPERSEDED block above `main` for why CI stopped passing 0.
	bool_require_resolved = os.environ.get("REVIEW_THREADS_REQUIRE_RESOLVED", "1") == "1"
	list_problems = find_thread_problems(
		list_threads, set_roster, bool_require_resolved=bool_require_resolved
	)

	return _print_thread_verdict(
		bool_json, list_problems, len(list_threads), bool_require_resolved
	)


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
