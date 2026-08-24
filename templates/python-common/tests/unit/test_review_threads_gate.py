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


def _review(str_login: str) -> dict:
	"""Build a submitted review authored by ``str_login``."""
	return {"author": {"login": str_login}}


def test_a_pr_nobody_reviewed_fails() -> None:
	"""Zero reviews from the roster must FAIL — the case the gate most needs to catch.

	Measured on PR #204: the reviewer was star-gated, posted only its refusal notice, and the
	PR merged with 29 of 30 checks green. Reading threads alone, "found nothing" and "never
	ran" are both zero, and the gate reported the second as ``All 0 review thread(s)
	answered.``
	"""
	cls_gate = _load_gate()
	str_problem = cls_gate.find_missing_review_problem([], _ROSTER, "some-human")
	assert str_problem is not None
	assert "never ran" in str_problem, "the message must not read like 'found nothing'"


def test_a_reviewer_that_found_nothing_passes() -> None:
	"""A submitted review with zero threads is a clean PR, not an absent reviewer.

	This is the half that makes the check above safe to require: without it the gate would be
	unsatisfiable on any PR a reviewer genuinely had no findings for.
	"""
	cls_gate = _load_gate()
	assert cls_gate.find_missing_review_problem([_review("coderabbitai")], _ROSTER, "h") is None


@pytest.mark.parametrize("str_login", ["coderabbitai", "coderabbitai[bot]"])
def test_the_review_author_spelling_does_not_matter(str_login: str) -> None:
	"""REST and GraphQL disagree on a bot login, and this predicate must survive both.

	The same mismatch made the thread half of this gate permanently green once already.
	"""
	cls_gate = _load_gate()
	assert cls_gate.find_missing_review_problem([_review(str_login)], _ROSTER, "h") is None


def test_a_review_from_outside_the_roster_is_not_the_declared_review() -> None:
	"""A passing human comment is not the reviewer this gate was told to expect."""
	cls_gate = _load_gate()
	assert cls_gate.find_missing_review_problem([_review("some-human")], _ROSTER, "h") is not None


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
			"nodes": [{"author": {"login": "human"}}],
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
			"nodes": [{"author": {"login": "coderabbitai"}}],
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
		cls_gate.find_missing_review_problem(dict_pr["reviews"]["nodes"], _ROSTER, "someone")
		is None
	)
	assert len(cls_gate.find_thread_problems(dict_pr["reviewThreads"]["nodes"], _ROSTER)) == 2


def test_a_roster_members_own_pr_is_exempt() -> None:
	"""A reviewer's own PR cannot require itself to review it.

	A gate nobody can satisfy is one people learn to bypass with ``--admin``, and the bypass
	habit swallows the real blocks too.
	"""
	cls_gate = _load_gate()
	assert cls_gate.find_missing_review_problem([], _ROSTER, "coderabbitai[bot]") is None


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


def test_ci_mode_asserts_only_the_half_it_can_re_evaluate() -> None:
	"""A job must not assert a condition nothing can re-trigger it to re-check.

	Resolving a thread emits `pull_request_review_thread`, which is not a workflow trigger, so
	nothing re-runs CI after a resolve. Asserting the resolve half there leaves a run red
	FOREVER on a PR that is finished — measured as 7 stale red runs on a single PR. A check that
	is red-by-design after you did the right thing is how people learn that red means nothing.

	So CI asserts REPLY only (a comment does re-trigger it), while the resolve half is enforced
	where it can be evaluated live: the branch ruleset and the local hooks.
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
	assert cls_gate.find_missing_review_problem([_review("github-actions")], set_reviewers, "h")


def test_the_missing_review_message_names_only_members_that_can_review() -> None:
	"""The gate must not tell people to wait for a member that never submits a review."""
	cls_gate = _load_gate()
	set_reviewers = cls_gate.reviewer_logins(_ROSTER_WITH_POSTS)
	assert "github-actions" not in cls_gate.find_missing_review_problem([], set_reviewers, "h")


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
	assert cls_gate.find_missing_review_problem([], set_reviewers, "github-actions[bot]")
