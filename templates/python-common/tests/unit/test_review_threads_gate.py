"""Unit tests for the review-thread answer gate (``bin/check_review_threads.py``).

The should-PASS cases carry the design. Two rules people reach for first — *"only a human may
resolve"* and *"the last comment must be human"* — **fail the best case**, because a good
reviewer bot acknowledges the author's reply and then resolves the thread itself, so its
comment is always last. A gate exercised only on what it rejects has been shown to reject, not
to discriminate.

Every shape here was measured on a real PR (blueprintx#170), including the one that motivated
the gate: 14 threads all reading ``isResolved: true`` while 11 held no author reply at all.
"""

import importlib.util
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pytest


# --------------------------
# Module Utilities
# --------------------------


def _load_gate() -> ModuleType:
	"""Import ``bin/check_review_threads.py`` as a module.

	Returns
	-------
	ModuleType
		The loaded gate module.
	"""
	path_gate = Path(__file__).resolve().parents[2] / "bin" / "check_review_threads.py"
	cls_spec = importlib.util.spec_from_file_location("_check_review_threads", path_gate)
	# Split rather than combined. A conjunction in one assertion reports only that the
	# whole thing was false, so a failure cannot say WHICH half broke — an absent loader
	# and an absent spec are different faults with different causes.
	assert cls_spec is not None
	assert cls_spec.loader is not None
	cls_module = importlib.util.module_from_spec(cls_spec)
	cls_spec.loader.exec_module(cls_module)
	return cls_module


_ROSTER = {"coderabbitai[bot]", "github-actions[bot]"}

# The same two members as ``_ROSTER``, in the shape ``load_roster`` now returns — normalised
# login to its ``posts:`` classification. The two are NOT interchangeable: the thread half of
# the gate takes every member, the missing-review half takes only those that can review.
_ROSTER_WITH_POSTS = {"coderabbitai": "threads", "github-actions": "status"}
_LONG = "x" * 150

# The PR head, and a commit it superseded. Two distinct oids because the gate's question is
# "which commit was this review written against?" — measured on blueprintx#219, where the only
# review was attributed to a commit pushed five minutes before the head.
_HEAD = "9ae76ab0000000000000000000000000000000000"
_SUPERSEDED = "9e7d1fe0000000000000000000000000000000000"


def _thread(list_comments: list[tuple[str, str]], *, bool_resolved: bool = True) -> dict:
	"""Build a review thread from ``(login, body)`` pairs.

	Parameters
	----------
	list_comments : list of tuple of (str, str)
		Author login and comment body, in order.
	bool_resolved : bool, optional
		Whether the thread is marked resolved, by default ``True``.

	Returns
	-------
	dict
		A thread shaped like the GraphQL response.
	"""
	return {
		"isResolved": bool_resolved,
		"isOutdated": False,
		"path": "src/thing.py",
		"comments": {"nodes": [{"author": {"login": a}, "body": b} for a, b in list_comments]},
	}


# --------------------------
# should-FAIL
# --------------------------


def test_a_thread_the_bot_resolved_alone_is_reported() -> None:
	"""The shape that motivated the gate: resolved by the reviewer, answered by nobody.

	Measured on blueprintx#170 — every thread read ``isResolved: true`` while 11 of 14 held no
	author reply. The resolved flag records the BOT's satisfaction on seeing the commit, never
	the author's reasoning, so keying on it would have passed all 14.
	"""
	cls_gate = _load_gate()
	list_threads = [
		_thread(
			[
				("coderabbitai[bot]", "**Correct the issue count.** " + _LONG),
				("coderabbitai[bot]", "✅ Addressed in commit 65ec2e9"),
			]
		)
	]
	list_problems = cls_gate.find_thread_problems(list_threads, _ROSTER)
	assert len(list_problems) == 1
	assert "nobody outside the reviewer roster answered it" in list_problems[0]


def test_a_terse_acknowledgement_is_not_an_answer() -> None:
	"""A one-word acknowledgement records no decision, so it cannot stand in for one.

	The floor is measured rather than invented: real replies ran 100-667 characters (median
	439) on the PR that motivated this, and 356-1126 on an earlier sample.
	"""
	cls_gate = _load_gate()
	list_threads = [
		_thread([("coderabbitai[bot]", "**Finding.** " + _LONG), ("guilhermegor", "done")])
	]
	assert len(cls_gate.find_thread_problems(list_threads, _ROSTER)) == 1


# --------------------------
# should-PASS
# --------------------------


def test_the_bot_may_acknowledge_and_resolve_after_a_real_answer() -> None:
	"""The BEST case must pass: author explains, bot confirms, bot resolves.

	This is why the gate keys on content rather than on resolver identity. "Only a human may
	resolve" fails here, and so does "the last comment must be human" — the bot's
	acknowledgement is always last.
	"""
	cls_gate = _load_gate()
	list_threads = [
		_thread(
			[
				("coderabbitai[bot]", "**Finding.** " + _LONG),
				("guilhermegor", "Corrigido em `65ec2e9`. " + _LONG),
				("coderabbitai[bot]", "Confirmed, the behaviour already covered both cases."),
			]
		)
	]
	assert cls_gate.find_thread_problems(list_threads, _ROSTER) == []


def test_an_answered_but_open_thread_is_now_reported() -> None:
	"""CONTRACT CHANGE: both halves are required — reply AND resolve.

	This test previously asserted the opposite, reasoning that resolving was covered by
	GitHub's ``required_conversation_resolution``. That reasoning holds only where the setting
	is actually enabled, and it was **off on this repo** — which is exactly how a PR merged
	with two live, unanswered threads. Delegating half a rule to a server-side toggle nobody
	verified is how the rule stops existing.

	Both layers now run: this gate fails fast in CI and on pre-push, and the ruleset
	provisioned by ``bin/enable_repo_rules.sh`` blocks the merge button. A thread whose
	discussion genuinely continues is a PR that is not ready to merge, so blocking is correct.
	"""
	cls_gate = _load_gate()
	list_threads = [
		_thread(
			[
				("coderabbitai[bot]", "**Finding.** " + _LONG),
				("guilhermegor", "Discordo, e aqui está o porquê: " + _LONG),
			],
			bool_resolved=False,
		)
	]
	list_problems = cls_gate.find_thread_problems(list_threads, _ROSTER)
	assert len(list_problems) == 1
	assert "NOT resolved" in list_problems[0]


def test_no_threads_is_not_a_THREAD_problem() -> None:
	"""A reviewer posting only a status check leaves no thread — not a THREAD failure.

	Measured: one tool posted five inline threads on a PR while another posted none at all. A
	roster that assumes every reviewer speaks in threads is born broken.

	⚠️ This function's silence on the empty set is correct but is NOT the whole verdict — see
	``find_missing_review_problem``, which owns "there were never any threads because nobody
	reviewed". Keeping the two apart is what lets each say something true.
	"""
	cls_gate = _load_gate()
	assert cls_gate.find_thread_problems([], _ROSTER) == []


# --------------------------
# 🔴 The empty set — a PR that merged with NO review at all
# --------------------------


def _review(str_login: str, str_oid: str = _HEAD) -> dict:
	"""Build a submitted review authored by ``str_login`` against ``str_oid``.

	Parameters
	----------
	str_login : str
		Review author's login, in either API's spelling.
	str_oid : str
		Commit the review is attributed to; defaults to the PR head.

	Returns
	-------
	dict
		A review shaped like the GraphQL response.
	"""
	return {"author": {"login": str_login}, "commit": {"oid": str_oid}}


def _notice(str_login: str, str_body: str) -> dict:
	"""Build one of the PR's issue comments.

	Parameters
	----------
	str_login : str
		Comment author's login.
	str_body : str
		Comment body.

	Returns
	-------
	dict
		An issue comment shaped like the GraphQL response.
	"""
	return {"author": {"login": str_login}, "body": str_body}


def test_a_pr_nobody_reviewed_fails() -> None:
	"""Zero reviews from the roster must FAIL — the case the gate most needs to catch.

	Measured on PR #204: the reviewer was star-gated, posted only its refusal notice, and the
	PR merged with 29 of 30 checks green. Reading threads alone, "found nothing" and "never
	ran" are both zero, and the gate reported the second as ``All 0 review thread(s)
	answered.``
	"""
	cls_gate = _load_gate()
	str_problem = cls_gate.find_missing_review_problem(
		[], _ROSTER, "some-human", str_head_oid=_HEAD
	)
	assert str_problem is not None
	assert "never ran" in str_problem, "the message must not read like 'found nothing'"


def test_a_reviewer_that_found_nothing_passes() -> None:
	"""A submitted review with zero threads is a clean PR, not an absent reviewer.

	This is the half that makes the check above safe to require: without it the gate would be
	unsatisfiable on any PR a reviewer genuinely had no findings for.
	"""
	cls_gate = _load_gate()
	assert (
		cls_gate.find_missing_review_problem(
			[_review("coderabbitai")], _ROSTER, "h", str_head_oid=_HEAD
		)
		is None
	)


@pytest.mark.parametrize("str_login", ["coderabbitai", "coderabbitai[bot]"])
def test_the_review_author_spelling_does_not_matter(str_login: str) -> None:
	"""REST and GraphQL disagree on a bot login, and this predicate must survive both.

	The same mismatch made the thread half of this gate permanently green once already.
	"""
	cls_gate = _load_gate()
	assert (
		cls_gate.find_missing_review_problem(
			[_review(str_login)], _ROSTER, "h", str_head_oid=_HEAD
		)
		is None
	)


def test_a_review_from_outside_the_roster_is_not_the_declared_review() -> None:
	"""A passing human comment is not the reviewer this gate was told to expect."""
	cls_gate = _load_gate()
	assert (
		cls_gate.find_missing_review_problem(
			[_review("some-human")], _ROSTER, "h", str_head_oid=_HEAD
		)
		is not None
	)


def test_the_query_excludes_unsubmitted_reviews() -> None:
	"""A PENDING review must not count as "a reviewer reported".

	Measured on blueprintx#216: opening a draft review and re-querying showed it in the
	``reviews`` connection, so without the ``states:`` filter the gate would read a reporting
	reviewer off something nobody can see — the vacuous pass it exists to remove.

	The filter lives in a GraphQL string that no unit test can execute, so this pins its
	presence instead: cheap, and it fails the moment someone "simplifies" the query.
	"""
	cls_gate = _load_gate()
	assert "states:[APPROVED, CHANGES_REQUESTED, COMMENTED, DISMISSED]" in cls_gate._QUERY
	assert "PENDING" not in cls_gate._QUERY


def test_both_connections_are_paginated(monkeypatch: pytest.MonkeyPatch) -> None:
	"""A PR with more than 100 reviews or threads must not be judged on page one alone.

	``first:100`` is a CAP, not "all". Truncated REVIEWS cause a false failure; truncated
	THREADS are worse and were not what the review flagged — thread 101 is simply never
	examined and the gate prints "All 100 ... answered" over unfinished conversations, which is
	the false pass this whole file exists to eliminate.

	The roster review is served ONLY on page two, so the last two assertions check that the
	merged data reaches the verdicts — without pagination this PR reads as never reviewed.
	"""
	cls_gate = _load_gate()
	# The two pages are DATA in a side_effect sequence, not a stub that branches on its cursor
	# arguments. The branch put a decision inside the test and the green never said which side
	# ran; the sequence states "page one, then page two" where a reader looks for it. Mock also
	# records the calls for free, so the hand-rolled call list is gone too.
	dict_page_one = {
		"author": {"login": "someone"},
		"reviews": {
			"pageInfo": {"hasNextPage": True, "endCursor": "R1"},
			"nodes": [_review("human")],
		},
		"reviewThreads": {
			"pageInfo": {"hasNextPage": True, "endCursor": "T1"},
			"nodes": [_thread([("coderabbitai", "**A.** " + _LONG)])],
		},
	}
	dict_page_two = {
		"author": {"login": "someone"},
		"reviews": {
			"pageInfo": {"hasNextPage": False, "endCursor": None},
			"nodes": [_review("coderabbitai")],
		},
		"reviewThreads": {
			"pageInfo": {"hasNextPage": False, "endCursor": None},
			"nodes": [_thread([("coderabbitai", "**B.** " + _LONG)])],
		},
	}
	cls_page = Mock(side_effect=[dict_page_one, dict_page_two])

	monkeypatch.setattr(cls_gate, "_fetch_page", cls_page)
	dict_pr = cls_gate.fetch_pull_request("o", "r", 1)

	list_calls = [tuple_args[3:5] for tuple_args, _ in cls_page.call_args_list]
	assert list_calls == [(None, None), ("R1", "T1")], "the second page must be requested"
	assert len(dict_pr["reviews"]["nodes"]) == 2, "page-two reviews must be merged in"
	assert len(dict_pr["reviewThreads"]["nodes"]) == 2, "page-two threads must be merged in"

	assert (
		cls_gate.find_missing_review_problem(
			dict_pr["reviews"]["nodes"], _ROSTER, "someone", str_head_oid=_HEAD
		)
		is None
	)
	assert len(cls_gate.find_thread_problems(dict_pr["reviewThreads"]["nodes"], _ROSTER)) == 2


def test_a_roster_members_own_pr_is_exempt() -> None:
	"""A reviewer's own PR cannot require itself to review it.

	A gate nobody can satisfy is one people learn to bypass with ``--admin``, and the bypass
	habit swallows the real blocks too.
	"""
	cls_gate = _load_gate()
	assert (
		cls_gate.find_missing_review_problem([], _ROSTER, "coderabbitai[bot]", str_head_oid=_HEAD)
		is None
	)


def test_an_absent_roster_makes_the_gate_a_no_op(tmp_path: Path) -> None:
	"""Without a declared roster the gate cannot tell a finding from an answer, so it skips.

	Guessing at logins would produce false failures on the repos that never adopted it.
	"""
	cls_gate = _load_gate()
	assert cls_gate.load_roster(tmp_path) == {}


def test_the_roster_is_read_from_the_declared_file(tmp_path: Path) -> None:
	"""The roster is data. No reviewer is named in the gate's logic, so swapping tools is a row."""
	cls_gate = _load_gate()
	(tmp_path / ".review-bots.yaml").write_text(
		"reviewers:\n  - login: some-other-reviewer[bot]\n    posts: threads\n",
		encoding="utf-8",
	)
	dict_roster = cls_gate.load_roster(tmp_path)
	assert dict_roster == {"some-other-reviewer": "threads"}, (
		"logins are normalised on load: GraphQL omits the bot-login suffix a declared "
		"reviewer carries, and comparing those spellings literally made this gate vacuous"
	)

	# And it behaves the same for that tool as for any other.
	list_threads = [_thread([("some-other-reviewer[bot]", "**Finding.** " + _LONG)])]
	assert len(cls_gate.find_thread_problems(list_threads, set(dict_roster))) == 1


def test_an_unreachable_api_is_not_mistaken_for_a_clean_pr() -> None:
	"""A failed query raises instead of returning an empty list.

	Returning ``[]`` on error would make an outage indistinguishable from "no threads" — the
	job reporting its own blindness as all-clear.
	"""
	cls_gate = _load_gate()
	with pytest.raises(RuntimeError):
		cls_gate.fetch_pull_request("no-such-owner-xyz", "no-such-repo-xyz", 1)


# --------------------------
# 🔴 The bot-login spelling — why this gate was silently vacuous
# --------------------------


def test_graphql_drops_the_bot_suffix_that_the_roster_carries() -> None:
	"""REST says ``coderabbitai[bot]``; GraphQL's ``author.login`` says ``coderabbitai``.

	The roster is written in the REST spelling because that is what GitHub shows everywhere
	else, but this gate reads GraphQL. A literal comparison therefore NEVER matched, so every
	reviewer comment counted as an "answer" and the gate reported "all threads answered" on a
	PR where nobody had replied to anything — permanently, silently green.

	⚠️ The existing fixtures could not catch it: they spell the login ``coderabbitai[bot]``,
	i.e. the test and the code shared the same wrong assumption about the data, and only
	production disagreed. These fixtures use the spelling GraphQL actually returns.
	"""
	cls_gate = _load_gate()
	assert cls_gate.normalise_login("coderabbitai[bot]") == "coderabbitai"
	assert cls_gate.normalise_login("coderabbitai") == "coderabbitai"
	# A human login is untouched, so nobody is accidentally treated as a reviewer.
	assert cls_gate.normalise_login("guilhermegor") == "guilhermegor"


def test_a_reviewer_comment_in_graphql_spelling_is_not_an_answer(tmp_path: Path) -> None:
	"""The production shape: roster in REST spelling, thread authors in GraphQL spelling.

	Parameters
	----------
	tmp_path : pathlib.Path
		Pytest throwaway dir holding the roster file.
	"""
	cls_gate = _load_gate()
	(tmp_path / ".review-bots.yaml").write_text(
		"reviewers:\n  - login: coderabbitai[bot]\n    posts: threads\n",
		encoding="utf-8",
	)
	set_roster = cls_gate.load_roster(tmp_path)

	# GraphQL spelling — no suffix. Before the fix this counted as an answer.
	list_threads = [_thread([("coderabbitai", "**Finding.** " + _LONG)])]
	assert len(cls_gate.find_thread_problems(list_threads, set_roster)) == 1


def test_a_human_reply_in_the_same_thread_still_answers_it(tmp_path: Path) -> None:
	"""The positive half: normalisation must not make every thread unanswerable.

	Parameters
	----------
	tmp_path : pathlib.Path
		Pytest throwaway dir holding the roster file.
	"""
	cls_gate = _load_gate()
	(tmp_path / ".review-bots.yaml").write_text(
		"reviewers:\n  - login: coderabbitai[bot]\n    posts: threads\n",
		encoding="utf-8",
	)
	set_roster = cls_gate.load_roster(tmp_path)

	list_threads = [_thread([("coderabbitai", "**Finding.** " + _LONG), ("guilhermegor", _LONG)])]
	assert cls_gate.find_thread_problems(list_threads, set_roster) == []


# --------------------------
# Both halves: replied AND resolved
# --------------------------


def test_an_answered_but_unresolved_thread_is_reported(tmp_path: Path) -> None:
	"""Replying is half the job — an open thread lets a PR merge mid-conversation.

	Parameters
	----------
	tmp_path : pathlib.Path
		Pytest throwaway dir holding the roster file.
	"""
	cls_gate = _load_gate()
	(tmp_path / ".review-bots.yaml").write_text(
		"reviewers:\n  - login: coderabbitai[bot]\n    posts: threads\n",
		encoding="utf-8",
	)
	set_roster = cls_gate.load_roster(tmp_path)

	list_threads = [
		_thread(
			[("coderabbitai", "**Finding.** " + _LONG), ("guilhermegor", _LONG)],
			bool_resolved=False,
		)
	]
	list_problems = cls_gate.find_thread_problems(list_threads, set_roster)
	assert len(list_problems) == 1
	assert "NOT resolved" in list_problems[0]


def test_deleting_the_roster_is_not_a_silent_opt_out(
	tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
	"""An absent roster means "never adopted" — unless the default branch still carries it.

	An empty roster makes the gate a no-op, so `rm .review-bots.yaml` is a one-line way to
	switch the gate off from inside the very PR it is meant to police. When git can prove the
	file exists on the default branch, its absence here is a DELETION and must be loud.

	Parameters
	----------
	tmp_path : pathlib.Path
		Pytest throwaway dir standing in for a checkout with no roster.
	monkeypatch : pytest.MonkeyPatch
		Used to stub the default-branch probe, so the test needs no real remote.
	"""
	cls_gate = _load_gate()

	# Never adopted → still a no-op, which keeps the gate opt-in for other repos.
	monkeypatch.setattr(cls_gate, "_roster_exists_on_default_branch", lambda _p: False)
	assert cls_gate.load_roster(tmp_path) == {}

	# Present upstream, absent here → deletion.
	monkeypatch.setattr(cls_gate, "_roster_exists_on_default_branch", lambda _p: True)
	with pytest.raises(RuntimeError, match="disables this gate"):
		cls_gate.load_roster(tmp_path)


def test_the_resolve_half_can_still_be_switched_off_by_flag() -> None:
	"""``bool_require_resolved=False`` must keep asserting the REPLY half and only that.

	⚠️ CI no longer passes ``False`` (#196): delegating the resolve half to
	``required_conversation_resolution`` looked safe because a merge-time setting cannot go
	stale, but that setting DROPS AN OUTDATED THREAD — measured on blueprintx#193, merge button
	enabled over an unresolved outdated thread with 29 of 29 checks green. The flag survives for
	callers that genuinely cannot re-evaluate a resolve, so the reply-only mode must keep
	working; dropping the resolve check must not quietly disable the job altogether.
	"""
	cls_gate = _load_gate()
	list_open_but_answered = [
		_thread(
			[("coderabbitai", "**Finding.** " + _LONG), ("guilhermegor", _LONG)],
			bool_resolved=False,
		)
	]
	# CI mode tolerates it — it could not tell you when it was fixed.
	assert (
		cls_gate.find_thread_problems(list_open_but_answered, _ROSTER, bool_require_resolved=False)
		== []
	)
	# Local mode still catches it — a local run is always current.
	assert len(cls_gate.find_thread_problems(list_open_but_answered, _ROSTER)) == 1

	# ⚠️ The half CI DOES own must still fire, or dropping the resolve check would have
	# quietly disabled the job altogether.
	list_unanswered = [_thread([("coderabbitai", "**Finding.** " + _LONG)])]
	assert (
		len(cls_gate.find_thread_problems(list_unanswered, _ROSTER, bool_require_resolved=False))
		== 1
	)


# --------------------------
# Tests — `posts:` splits the roster in two (#218)
# --------------------------


def test_a_status_only_member_cannot_satisfy_the_missing_review_gate() -> None:
	"""The negative control: a review by a ``posts: status`` member is not a review.

	``github-actions[bot]`` can submit a review with the ambient ``GITHUB_TOKEN``, so before
	this split any workflow that posted one satisfied a gate whose entire purpose is "a real
	reviewer looked at this" — the same class of hole as #208, reached from the other side.
	"""
	cls_gate = _load_gate()
	set_reviewers = cls_gate.reviewer_logins(_ROSTER_WITH_POSTS)
	assert cls_gate.find_missing_review_problem(
		[_review("github-actions")], set_reviewers, "h", str_head_oid=_HEAD
	)


def test_the_missing_review_message_names_only_members_that_can_review() -> None:
	"""The gate must not tell people to wait for a member that never submits a review."""
	cls_gate = _load_gate()
	set_reviewers = cls_gate.reviewer_logins(_ROSTER_WITH_POSTS)
	assert "github-actions" not in cls_gate.find_missing_review_problem(
		[], set_reviewers, "h", str_head_oid=_HEAD
	)


def test_a_thread_answer_from_a_status_member_is_still_not_an_answer() -> None:
	"""The THREAD half keeps the whole roster — a status member's comment is not the author's.

	The two halves take different sets on purpose, and this pins the half that must NOT narrow.
	"""
	cls_gate = _load_gate()
	list_threads = [
		_thread([("coderabbitai", "**Finding.** " + _LONG), ("github-actions", _LONG)])
	]
	assert len(cls_gate.find_thread_problems(list_threads, set(_ROSTER_WITH_POSTS))) == 1


def test_reviewer_logins_keeps_only_the_threads_members() -> None:
	"""The split itself, asserted directly rather than only through its two consumers."""
	cls_gate = _load_gate()
	assert cls_gate.reviewer_logins(_ROSTER_WITH_POSTS) == {"coderabbitai"}


def test_a_roster_where_nobody_can_review_fails_loudly() -> None:
	"""A roster of only status members makes the gate unsatisfiable, so it must not load.

	A required check that can never go green is the fastest way to teach people that red
	means nothing — and the bypass habit that follows swallows the real blocks too.
	"""
	cls_gate = _load_gate()
	with pytest.raises(RuntimeError, match="no member with posts"):
		cls_gate.reviewer_logins({"github-actions": "status"})


def test_a_row_without_posts_is_rejected_rather_than_defaulted(tmp_path: Path) -> None:
	"""Neither default is safe, so the roster must say. See ``posts_of``.

	Reading a forgotten field as ``status`` makes the gate unsatisfiable; reading it as
	``threads`` re-opens the exact hole the field exists to close.
	"""
	cls_gate = _load_gate()
	(tmp_path / ".review-bots.yaml").write_text(
		"reviewers:\n  - login: some-reviewer[bot]\n", encoding="utf-8"
	)
	with pytest.raises(RuntimeError, match="some-reviewer"):
		cls_gate.load_roster(tmp_path)


def test_an_unrecognised_posts_value_is_rejected(tmp_path: Path) -> None:
	"""A typo'd classification must name itself, not fall through to a silent behaviour."""
	cls_gate = _load_gate()
	(tmp_path / ".review-bots.yaml").write_text(
		"reviewers:\n  - login: some-reviewer[bot]\n    posts: reviews\n", encoding="utf-8"
	)
	with pytest.raises(RuntimeError, match="reviews"):
		cls_gate.load_roster(tmp_path)


def test_a_status_member_opening_a_pr_is_not_exempt() -> None:
	"""The exemption is "do not ask X to review X", never "bots are exempt".

	``github-actions[bot]`` opens workflow PRs and cannot review, so a real reviewer can look
	at its PR and there is nothing unsatisfiable about asking.
	"""
	cls_gate = _load_gate()
	set_reviewers = cls_gate.reviewer_logins(_ROSTER_WITH_POSTS)
	assert cls_gate.find_missing_review_problem(
		[], set_reviewers, "github-actions[bot]", str_head_oid=_HEAD
	)


def test_an_emptied_roster_is_rejected_like_a_deleted_one(tmp_path: Path) -> None:
	"""``reviewers: []`` is the deletion guard's hole, reached with different keystrokes.

	The file is present, so the default-branch deletion check never fires, and an empty result
	reads to ``main`` as "not adopted here" — a gate switched off inside the very PR it polices.
	Opting out is deleting the file, which self-skips with a message. Raised by review on #262.
	"""
	cls_gate = _load_gate()
	(tmp_path / ".review-bots.yaml").write_text("reviewers: []\n", encoding="utf-8")
	with pytest.raises(RuntimeError, match="declares no reviewers"):
		cls_gate.load_roster(tmp_path)


# --------------------------
# Tests — a review is pinned to a COMMIT (#220)
# --------------------------


def test_a_review_of_a_superseded_commit_does_not_satisfy_the_gate() -> None:
	"""The negative control: this input PASSED before the head check existed.

	Measured on blueprintx#219 while the gate was first being exercised: ``head=9ae76ab`` and the
	PR's only review attributed to ``9e7d1fe``, a commit superseded five minutes earlier. Both
	trigger runs had fired and both succeeded — triggering a review is necessary and NOT
	sufficient, because nothing checked what came back was about the current code.
	"""
	cls_gate = _load_gate()
	assert (
		cls_gate.find_missing_review_problem(
			[_review("coderabbitai", _SUPERSEDED)], _ROSTER, "h", str_head_oid=_HEAD
		)
		is not None
	)


def test_a_review_of_the_head_commit_satisfies_the_gate() -> None:
	"""The should-PASS half: the check must discriminate, not merely reject.

	Without this, tightening the predicate to "no review ever counts" would also go green.
	"""
	cls_gate = _load_gate()
	assert (
		cls_gate.find_missing_review_problem(
			[_review("coderabbitai", _HEAD)], _ROSTER, "h", str_head_oid=_HEAD
		)
		is None
	)


def test_reviewed_older_code_and_never_reviewed_print_different_sentences() -> None:
	"""Two facts with different remedies must not print identically.

	This is the defect #208 rewrote this message for once already, one level up: "the reviewer
	ran, on older code" tells you to wait for the push-triggered re-review, while "no reviewer
	ever ran" tells you to trigger one. A reader given the wrong sentence wastes the trigger.
	"""
	cls_gate = _load_gate()
	str_stale = cls_gate.find_missing_review_problem(
		[_review("coderabbitai", _SUPERSEDED)], _ROSTER, "h", str_head_oid=_HEAD
	)
	assert "SUPERSEDED" in str_stale, "the stale-review message must not read like 'no review'"


def test_the_stale_review_message_names_the_head_commit() -> None:
	"""A message that cannot be acted on is a message nobody reads.

	Naming the head oid is what lets a reader compare it against the review's own attribution
	on the PR page, rather than taking the gate's word for it.
	"""
	cls_gate = _load_gate()
	str_stale = cls_gate.find_missing_review_problem(
		[_review("coderabbitai", _SUPERSEDED)], _ROSTER, "h", str_head_oid=_HEAD
	)
	assert _HEAD[:7] in str_stale


def test_the_query_asks_for_the_commit_each_review_was_written_against() -> None:
	"""The head check is worthless if the field stops being fetched.

	The query is a GraphQL string no unit test can execute, so its content is pinned here —
	the same technique that guards the ``states:`` filter against a well-meant simplification.
	"""
	cls_gate = _load_gate()
	assert "commit { oid }" in cls_gate._QUERY


def test_the_query_asks_for_the_head_commit() -> None:
	"""Without ``headRefOid`` there is nothing to compare a review's commit against."""
	cls_gate = _load_gate()
	assert "headRefOid" in cls_gate._QUERY


# --------------------------
# Tests — a redundant re-review is not an unreviewed PR (#259)
# --------------------------


# The reviewer's ACTUAL boilerplate, copied verbatim from blueprintx#264's own comment stream.
# It is appended to EVERY outcome — performed, rate-limited and failed alike — which is what
# defeated the first draft of this check.
_FOOTNOTE = (
	"> Note: CodeRabbit is an incremental review system and does not re-review already "
	"reviewed commits. This command is applicable only when automatic reviews are paused."
)
_NOTICE_PERFORMED = (
	f"<summary>\u2705 Action performed</summary>\n\nReview finished.\n\n{_FOOTNOTE}"
)
_NOTICE_LIMITED = (
	f"<summary>\u26a0\ufe0f Action not completed</summary>\n\nReview rate limited.\n\n{_FOOTNOTE}"
)
_NOTICE_FAILED = f"<summary>\u274c Action failed</summary>\n\nReview failed.\n\n{_FOOTNOTE}"


@pytest.mark.parametrize(
	"str_notice",
	[_NOTICE_PERFORMED, _NOTICE_LIMITED, _NOTICE_FAILED],
	ids=["performed", "rate_limited", "failed"],
)
def test_the_already_reviewed_footnote_never_satisfies_the_gate(str_notice: str) -> None:
	"""The negative control for the defect this check shipped with and review caught.

	"does not re-review already reviewed commits" is a STANDING FOOTNOTE about how the product
	works, appended to every outcome — not a statement about this PR. Keying a pass on it made a
	rate-limited and an outright FAILED review read as "declined as redundant". Measured on
	blueprintx#264 by reading its own comment stream: all three notices carry it verbatim.

	Parameters
	----------
	str_notice : str
		One of the three real notices, copied from the measured stream.
	"""
	cls_gate = _load_gate()
	assert (
		cls_gate.find_missing_review_problem(
			[],
			_ROSTER,
			"h",
			str_head_oid=_HEAD,
			list_notices=[_notice("coderabbitai", str_notice)],
		)
		is not None
	)


def test_the_failure_message_quotes_the_reviewers_latest_notice() -> None:
	"""The notice is worth SHOWING even though it is not worth trusting.

	`reviews == 0` collapses states with different remedies — never ran, refused, rate-limited,
	declined. The reader cannot tell which without the reviewer's own words, so they are quoted;
	the verdict is unaffected.
	"""
	cls_gate = _load_gate()
	str_problem = cls_gate.find_missing_review_problem(
		[],
		_ROSTER,
		"h",
		str_head_oid=_HEAD,
		list_notices=[_notice("coderabbitai", _NOTICE_LIMITED)],
	)
	assert "Review rate limited." in str_problem


def test_the_quoted_notice_is_stripped_of_markup() -> None:
	"""A notice pasted raw drags hidden HTML markers into a CI log nobody can read."""
	cls_gate = _load_gate()
	str_problem = cls_gate.find_missing_review_problem(
		[],
		_ROSTER,
		"h",
		str_head_oid=_HEAD,
		list_notices=[_notice("coderabbitai", _NOTICE_FAILED)],
	)
	assert "<summary>" not in str_problem


def test_only_a_roster_notice_is_quoted() -> None:
	"""A comment from anyone else is not the reviewer's word about its own run."""
	cls_gate = _load_gate()
	str_problem = cls_gate.find_missing_review_problem(
		[],
		_ROSTER,
		"h",
		str_head_oid=_HEAD,
		list_notices=[_notice("some-human", "these commits were already reviewed on the old PR")],
	)
	assert "already reviewed on the old PR" not in str_problem


def test_the_newest_roster_notice_is_the_one_quoted() -> None:
	"""An older notice describes a state the reviewer has since superseded."""
	cls_gate = _load_gate()
	str_problem = cls_gate.find_missing_review_problem(
		[],
		_ROSTER,
		"h",
		str_head_oid=_HEAD,
		list_notices=[
			_notice("coderabbitai", _NOTICE_PERFORMED),
			_notice("coderabbitai", _NOTICE_LIMITED),
		],
	)
	assert "Review rate limited." in str_problem


def test_the_remedy_names_a_full_review_not_an_incremental_one() -> None:
	"""An incremental reviewer answers "already reviewed" on commits seen on another PR.

	#259 argued this gate would be unsatisfiable because the remedy it printed was the command
	that fails. A different documented command does not: `@coderabbitai full review` "disregards
	any comments that CodeRabbit has already made on this pull request, and generates a complete
	review of the entire pull request". Printing the wrong one is what makes a gate look
	unsatisfiable, and unsatisfiable gates get bypassed with --admin.
	"""
	cls_gate = _load_gate()
	str_problem = cls_gate.find_missing_review_problem([], _ROSTER, "h", str_head_oid=_HEAD)
	assert "@coderabbitai full review" in str_problem


def test_the_superseded_message_also_names_a_full_review() -> None:
	"""The remedy is printed by TWO messages, and a test on one proves nothing about the other.

	⚠️ Found by a negative control that PASSED: downgrading `full review` to `review` in the
	superseded-code branch changed nothing red, because the only test asserting the remedy
	exercised the zero-review branch. Both branches carry the same sentence and it can rot
	independently in either — which is the "shrink the mutation until only the target test can
	fail" rule read from the other end: a mutation that fails nothing has found a gap, not a
	clean bill of health.
	"""
	cls_gate = _load_gate()
	str_problem = cls_gate.find_missing_review_problem(
		[_review("coderabbitai", _SUPERSEDED)], _ROSTER, "h", str_head_oid=_HEAD
	)
	assert "@coderabbitai full review" in str_problem


def test_the_query_asks_for_the_prs_issue_comments() -> None:
	"""The notices are ISSUE comments, not review threads — verified on blueprintx#257.

	Reading only ``reviewThreads`` cannot see them, which is why the distinction between
	"nobody looked" and "already looked" was unavailable to the gate at all.
	"""
	cls_gate = _load_gate()
	assert "comments(last:100)" in cls_gate._QUERY


# --------------------------
# Tests — an outdated thread is the one the merge button drops (#196)
# --------------------------


def test_an_outdated_unresolved_thread_is_reported() -> None:
	"""GitHub drops it from the blocking set, so this gate is the only thing left asserting it.

	Measured on blueprintx#193: ``required_conversation_resolution: enabled``,
	``enforce_admins: True``, 29 of 29 checks green — and "Squash and merge" enabled over a
	thread reading ``resolved=False outdated=True``. Outdating is caused by the author's own
	commit rewriting the commented lines, so it is exactly the state an author can manufacture.
	"""
	cls_gate = _load_gate()
	dict_outdated = _thread(
		[("coderabbitai", "**Finding.** " + _LONG), ("guilhermegor", _LONG)],
		bool_resolved=False,
	)
	dict_outdated["isOutdated"] = True
	assert len(cls_gate.find_thread_problems([dict_outdated], _ROSTER)) == 1


def test_the_outdated_thread_message_says_the_merge_button_will_not_block() -> None:
	"""A reader who believes the native setting covers this will not act on the finding.

	The field was queried and never read in any predicate — the gate could see the state and
	said nothing about it, which is how the guarantee came to be described as stronger than it
	was.
	"""
	cls_gate = _load_gate()
	dict_outdated = _thread(
		[("coderabbitai", "**Finding.** " + _LONG), ("guilhermegor", _LONG)],
		bool_resolved=False,
	)
	dict_outdated["isOutdated"] = True
	assert "OUTDATED" in cls_gate.find_thread_problems([dict_outdated], _ROSTER)[0]


def test_a_current_unresolved_thread_does_not_claim_to_be_outdated() -> None:
	"""The should-PASS half of the message: the warning must discriminate, not always print."""
	cls_gate = _load_gate()
	list_current = [
		_thread(
			[("coderabbitai", "**Finding.** " + _LONG), ("guilhermegor", _LONG)],
			bool_resolved=False,
		)
	]
	assert "OUTDATED" not in cls_gate.find_thread_problems(list_current, _ROSTER)[0]
