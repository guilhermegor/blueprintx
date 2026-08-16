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
	assert cls_spec is not None and cls_spec.loader is not None
	cls_module = importlib.util.module_from_spec(cls_spec)
	cls_spec.loader.exec_module(cls_module)
	return cls_module


_ROSTER = {"coderabbitai[bot]", "github-actions[bot]"}
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


def test_an_answer_on_a_still_open_thread_counts() -> None:
	"""Answering is the requirement; resolving is a separate act.

	A thread left open after a substantive reply — because the discussion continues — is not
	what this gate exists to catch. ``required_conversation_resolution`` covers that half.
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
	assert cls_gate.find_thread_problems(list_threads, _ROSTER) == []


def test_a_pr_with_no_threads_passes() -> None:
	"""A reviewer that posts only a status check leaves no thread, and that is not a failure.

	Measured: one tool posted five inline threads on a PR while another posted none at all. A
	roster that assumes every reviewer speaks in threads is born broken.
	"""
	cls_gate = _load_gate()
	assert cls_gate.find_thread_problems([], _ROSTER) == []


def test_an_absent_roster_makes_the_gate_a_no_op(tmp_path: Path) -> None:
	"""Without a declared roster the gate cannot tell a finding from an answer, so it skips.

	Guessing at logins would produce false failures on the repos that never adopted it.
	"""
	cls_gate = _load_gate()
	assert cls_gate.load_roster(tmp_path) == set()


def test_the_roster_is_read_from_the_declared_file(tmp_path: Path) -> None:
	"""The roster is data. No reviewer is named in the gate's logic, so swapping tools is a row."""
	cls_gate = _load_gate()
	(tmp_path / ".review-bots.yaml").write_text(
		"reviewers:\n  - login: some-other-reviewer[bot]\n    posts: threads\n",
		encoding="utf-8",
	)
	set_roster = cls_gate.load_roster(tmp_path)
	assert set_roster == {"some-other-reviewer[bot]"}

	# And it behaves the same for that tool as for any other.
	list_threads = [_thread([("some-other-reviewer[bot]", "**Finding.** " + _LONG)])]
	assert len(cls_gate.find_thread_problems(list_threads, set_roster)) == 1


def test_an_unreachable_api_is_not_mistaken_for_a_clean_pr() -> None:
	"""A failed query raises instead of returning an empty list.

	Returning ``[]`` on error would make an outage indistinguishable from "no threads" — the
	job reporting its own blindness as all-clear.
	"""
	cls_gate = _load_gate()
	with pytest.raises(RuntimeError):
		cls_gate.fetch_threads("no-such-owner-xyz", "no-such-repo-xyz", 1)
