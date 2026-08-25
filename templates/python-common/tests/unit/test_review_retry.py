"""Unit tests for the rate-limited-review retry (``bin/retry_rate_limited_review.py``).

The whole design rests on one measurement, so the tests are organised around what that
measurement licenses and what it forbids:

- Licensed: re-ASKING when the reviewer said it was rate limited. Measured upstream over 112
  PRs — 19 hit a rate limit and 18 were reviewed in the end, so the state is a delay.
- Forbidden: letting any of this influence a VERDICT. blueprintx#259 established that a
  reviewer notice's text cannot decide whether a PR was reviewed, because the "already
  reviewed" footnote is appended to every outcome. The rate-limit phrase does discriminate
  (0/25 performed, 0/3 failed, 57/59 not-completed), but this module still only ever asks for a
  review — never passes one.

So the load-bearing test here is the negative one: a PR with **no review at all and no notice**
must not be re-asked into looking healthy, and one whose reviewer merely *reviewed older code*
is not a rate-limit case either.
"""

from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
from types import ModuleType

import pytest


# --------------------------
# Module Utilities
# --------------------------


def _load_retry() -> ModuleType:
	"""Import ``bin/retry_rate_limited_review.py`` as a module.

	Returns
	-------
	ModuleType
		The loaded retry module.
	"""
	path_mod = Path(__file__).resolve().parents[2] / "bin" / "retry_rate_limited_review.py"
	cls_spec = importlib.util.spec_from_file_location("_retry_rate_limited_review", path_mod)
	# Split rather than combined, matching the gate's own test module. An absent spec and an
	# absent loader are different faults, and a conjunction cannot say which one fired.
	assert cls_spec is not None
	assert cls_spec.loader is not None
	cls_module = importlib.util.module_from_spec(cls_spec)
	cls_spec.loader.exec_module(cls_module)
	return cls_module


_DT_NOW = datetime(2026, 8, 24, 23, 55, 0, tzinfo=timezone.utc)


def _comment(str_login: str, str_body: str, int_min_ago: int = 0) -> dict:
	"""Build one normalised issue comment.

	Parameters
	----------
	str_login : str
		The comment author's login.
	str_body : str
		The comment body.
	int_min_ago : int
		How many minutes before ``_DT_NOW`` it was posted.

	Returns
	-------
	dict
		A comment with ``login``, ``body`` and ``created_at``.
	"""
	dt_at = _DT_NOW - timedelta(minutes=int_min_ago)
	return {
		"login": str_login,
		"body": str_body,
		"created_at": dt_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
	}


def _pr(list_comments: list, list_reviews: list, str_head: str = "cafe123") -> dict:
	"""Build a ``pullRequest`` node with the fields the retry predicate reads.

	Parameters
	----------
	list_comments : list
		Accepted for call-site symmetry; comments are passed to the predicate separately.
	list_reviews : list
		Submitted-review nodes.
	str_head : str
		The head commit oid.

	Returns
	-------
	dict
		A pull-request node.
	"""
	return {"headRefOid": str_head, "reviews": {"nodes": list_reviews}}


# The real reviewer wording, kept verbatim rather than paraphrased: the phrase IS the interface,
# and a paraphrase would let the detector drift away from what the reviewer actually posts.
_STR_RATE_LIMITED = (
	"⚠️ Action not completed\n\nReview rate limited. Please wait before your next review "
	"request. Note: CodeRabbit is an incremental review system and does not re-review "
	"already reviewed commits."
)
_STR_PERFORMED = (
	"✅ Action performed\n\nReview triggered. Note: CodeRabbit is an incremental review system "
	"and does not re-review already reviewed commits."
)


# --------------------------
# Fixtures
# --------------------------


@pytest.fixture
def cls_retry() -> ModuleType:
	"""Provide the loaded retry module.

	Returns
	-------
	ModuleType
		The retry module.
	"""
	return _load_retry()


@pytest.fixture
def cls_gate() -> ModuleType:
	"""Provide the loaded review gate, whose helpers the retry module reuses.

	Returns
	-------
	ModuleType
		The gate module.
	"""
	path_gate = Path(__file__).resolve().parents[2] / "bin" / "check_review_threads.py"
	cls_spec = importlib.util.spec_from_file_location("_gate_for_retry", path_gate)
	assert cls_spec is not None
	assert cls_spec.loader is not None
	cls_module = importlib.util.module_from_spec(cls_spec)
	cls_spec.loader.exec_module(cls_module)
	return cls_module


# --------------------------
# Tests
# --------------------------


def test_a_rate_limited_pr_with_no_review_is_re_asked(
	cls_retry: ModuleType, cls_gate: ModuleType
) -> None:
	"""The case the file exists for: reviewer throttled, nothing reviewed, so ask again.

	Parameters
	----------
	cls_retry : types.ModuleType
		The retry module.
	cls_gate : types.ModuleType
		The gate module.
	"""
	list_comments = [_comment("coderabbitai", _STR_RATE_LIMITED)]
	dict_pr = _pr(list_comments, [])

	assert (
		cls_retry.pr_needs_retry(
			dict_pr, list_comments, {"coderabbitai"}, cls_gate, "guilhermegor", _DT_NOW
		)
		is True
	)


def test_a_reviewed_head_is_never_re_asked(cls_retry: ModuleType, cls_gate: ModuleType) -> None:
	"""A review on the head commit ends the matter, whatever the notices say.

	Parameters
	----------
	cls_retry : types.ModuleType
		The retry module.
	cls_gate : types.ModuleType
		The gate module.
	"""
	list_comments = [_comment("coderabbitai", _STR_RATE_LIMITED)]
	dict_pr = _pr(
		list_comments, [{"author": {"login": "coderabbitai"}, "commit": {"oid": "cafe123"}}]
	)

	assert (
		cls_retry.pr_needs_retry(
			dict_pr, list_comments, {"coderabbitai"}, cls_gate, "guilhermegor", _DT_NOW
		)
		is False
	)


def test_a_pr_with_no_notice_at_all_is_not_re_asked(
	cls_retry: ModuleType, cls_gate: ModuleType
) -> None:
	"""Zero reviews and SILENCE is not a rate limit — the load-bearing negative.

	This is the #259 boundary. A PR nobody has looked at and nobody has commented on is the
	state the gate must keep blocking; re-asking is harmless but claiming a cause we cannot
	see is how a text matcher turns into a verdict. The predicate must read silence as
	"not my case", not as "probably throttled".

	Parameters
	----------
	cls_retry : types.ModuleType
		The retry module.
	cls_gate : types.ModuleType
		The gate module.
	"""
	list_comments = []
	dict_pr = _pr(list_comments, [])

	assert (
		cls_retry.pr_needs_retry(
			dict_pr, list_comments, {"coderabbitai"}, cls_gate, "guilhermegor", _DT_NOW
		)
		is False
	)


def test_a_successful_trigger_notice_is_not_a_rate_limit(
	cls_retry: ModuleType, cls_gate: ModuleType
) -> None:
	"""``Action performed`` must not be read as throttled, though it shares the footnote.

	Both notices end with the same "does not re-review already reviewed commits" sentence —
	the footnote #259 proved worthless as a signal. Only the rate-limit wording may fire, so
	this test pins the discrimination the measurement claims.

	Parameters
	----------
	cls_retry : types.ModuleType
		The retry module.
	cls_gate : types.ModuleType
		The gate module.
	"""
	list_comments = [_comment("coderabbitai", _STR_PERFORMED)]
	dict_pr = _pr(list_comments, [])

	assert (
		cls_retry.pr_needs_retry(
			dict_pr, list_comments, {"coderabbitai"}, cls_gate, "guilhermegor", _DT_NOW
		)
		is False
	)


def test_only_the_newest_notice_decides(cls_retry: ModuleType, cls_gate: ModuleType) -> None:
	"""A rate limit the reviewer has since superseded must not trigger a re-ask.

	Same rule the gate already applies to its quoted notice: an older sentence describes a
	state that no longer holds. Comments arrive oldest-first, so the scan runs backwards.

	Parameters
	----------
	cls_retry : types.ModuleType
		The retry module.
	cls_gate : types.ModuleType
		The gate module.
	"""
	list_comments = [
		_comment("coderabbitai", _STR_RATE_LIMITED),
		_comment("coderabbitai", _STR_PERFORMED),
	]
	dict_pr = _pr(list_comments, [])

	assert (
		cls_retry.pr_needs_retry(
			dict_pr, list_comments, {"coderabbitai"}, cls_gate, "guilhermegor", _DT_NOW
		)
		is False
	)


def test_the_marker_makes_a_scheduled_run_ask_once_per_window(
	cls_retry: ModuleType, cls_gate: ModuleType
) -> None:
	"""Our own request, posted after the notice, stops the next tick asking again.

	Without this the workflow would comment every 10 minutes for the whole window. The check
	is ordering, not timestamps: the marker sitting above the notice IS "already asked".

	Parameters
	----------
	cls_retry : types.ModuleType
		The retry module.
	cls_gate : types.ModuleType
		The gate module.
	"""
	list_comments = [
		_comment("coderabbitai", _STR_RATE_LIMITED),
		_comment("guilhermegor", cls_retry._STR_REQUEST),
	]
	dict_pr = _pr(list_comments, [])

	assert (
		cls_retry.pr_needs_retry(
			dict_pr, list_comments, {"coderabbitai"}, cls_gate, "guilhermegor", _DT_NOW
		)
		is False
	)


def test_the_reviewers_own_acknowledgement_does_not_trigger_another_ask(
	cls_retry: ModuleType, cls_gate: ModuleType
) -> None:
	"""🔴 The loop this file shipped once: the ack to our request is NOT a new window.

	Measured live on blueprintx#270 — the reviewer acknowledges a request within ~13 seconds,
	and that acknowledgement is a roster comment NEWER than our marker, carrying the
	rate-limit wording. The first implementation asked "is our marker newer than the newest
	roster notice?", so it met the ack, concluded "not asked yet", and asked again every tick,
	for ever.

	⚠️ The test that replaced here asserted the DEFECT — it was written from the same mental
	model as the code, so it agreed with it. A cooldown cannot be fooled this way: we asked
	recently or we did not.

	Parameters
	----------
	cls_retry : types.ModuleType
		The retry module.
	cls_gate : types.ModuleType
		The gate module.
	"""
	list_comments = [
		_comment("coderabbitai", _STR_RATE_LIMITED, int_min_ago=6),
		_comment("guilhermegor", cls_retry._STR_REQUEST, int_min_ago=5),
		_comment("coderabbitai", _STR_RATE_LIMITED, int_min_ago=4),
	]
	dict_pr = _pr(list_comments, [])

	assert (
		cls_retry.pr_needs_retry(
			dict_pr, list_comments, {"coderabbitai"}, cls_gate, "guilhermegor", _DT_NOW
		)
		is False
	)


def test_the_cooldown_expires_so_a_stuck_pr_is_asked_again(
	cls_retry: ModuleType, cls_gate: ModuleType
) -> None:
	"""The other half: once the window has genuinely passed, ask again.

	Without this the cooldown would be a permanent silence after one request — the failure
	mode the marker-authorship guard exists to prevent, reintroduced by its replacement.

	Parameters
	----------
	cls_retry : types.ModuleType
		The retry module.
	cls_gate : types.ModuleType
		The gate module.
	"""
	list_comments = [
		_comment("guilhermegor", cls_retry._STR_REQUEST, int_min_ago=45),
		_comment("coderabbitai", _STR_RATE_LIMITED, int_min_ago=44),
	]
	dict_pr = _pr(list_comments, [])

	assert (
		cls_retry.pr_needs_retry(
			dict_pr, list_comments, {"coderabbitai"}, cls_gate, "guilhermegor", _DT_NOW
		)
		is True
	)


def test_a_review_on_older_code_is_not_a_rate_limit_case(
	cls_retry: ModuleType, cls_gate: ModuleType
) -> None:
	"""A review pinned to a superseded commit, with no throttle notice, is left alone.

	The gate reports this state with its own distinct message (#208), and it calls for a
	different action. Re-asking on it would be harmless, but treating "reviewed older code"
	as "throttled" would blur two states the gate deliberately separated.

	Parameters
	----------
	cls_retry : types.ModuleType
		The retry module.
	cls_gate : types.ModuleType
		The gate module.
	"""
	list_comments = [_comment("coderabbitai", _STR_PERFORMED)]
	dict_pr = _pr(
		list_comments, [{"author": {"login": "coderabbitai"}, "commit": {"oid": "0ldc0de"}}]
	)

	assert (
		cls_retry.pr_needs_retry(
			dict_pr, list_comments, {"coderabbitai"}, cls_gate, "guilhermegor", _DT_NOW
		)
		is False
	)


def test_the_request_names_a_full_review_not_a_plain_one(cls_retry: ModuleType) -> None:
	"""The posted command must be the FULL form, which ignores what was already reviewed.

	Pinned to the exact command a user could type, never a noun phrase: the module's own
	docstring contains the words "full review" in prose, and an assertion satisfied by that
	prose would pass while the command was downgraded — the over-available-needle trap
	measured in blueprintx#264.

	Parameters
	----------
	cls_retry : types.ModuleType
		The retry module.
	"""
	assert "@coderabbitai full review" in cls_retry._STR_REQUEST


def test_the_request_carries_the_idempotence_marker(cls_retry: ModuleType) -> None:
	"""The posted body must contain the marker, or every tick re-asks.

	Parameters
	----------
	cls_retry : types.ModuleType
		The retry module.
	"""
	assert cls_retry._STR_MARKER in cls_retry._STR_REQUEST


def test_a_marker_from_another_author_does_not_suppress_the_retry(
	cls_retry: ModuleType, cls_gate: ModuleType
) -> None:
	"""🔴 The security case: anyone who can comment can post the marker text.

	A marker is an HTML comment in a comment body, so it is not a capability — it is a string
	any PR commenter can type. Trusting the text alone let a single comment silence the retry
	for that PR permanently: the newest-first scan stops at the marker before it ever reaches
	the reviewer's notice, and nothing says so. Only a marker authored by the identity the
	retry posts as may count.

	Parameters
	----------
	cls_retry : types.ModuleType
		The retry module.
	cls_gate : types.ModuleType
		The gate module.
	"""
	list_comments = [
		_comment("coderabbitai", _STR_RATE_LIMITED),
		_comment("a-passer-by", cls_retry._STR_REQUEST),
	]
	dict_pr = _pr(list_comments, [])

	assert (
		cls_retry.pr_needs_retry(
			dict_pr, list_comments, {"coderabbitai"}, cls_gate, "guilhermegor", _DT_NOW
		)
		is True
	)


def test_an_unresolvable_identity_trusts_no_marker(
	cls_retry: ModuleType, cls_gate: ModuleType
) -> None:
	"""With no known self-login, even our own marker is ignored — ask twice, never fall silent.

	The failure direction is the point. Trusting every marker when the identity is unknown
	restores the hole above; trusting none costs a duplicate request. Noise is recoverable,
	silence is not.

	Parameters
	----------
	cls_retry : types.ModuleType
		The retry module.
	cls_gate : types.ModuleType
		The gate module.
	"""
	list_comments = [
		_comment("coderabbitai", _STR_RATE_LIMITED),
		_comment("guilhermegor", cls_retry._STR_REQUEST),
	]
	dict_pr = _pr(list_comments, [])

	assert (
		cls_retry.pr_needs_retry(dict_pr, list_comments, {"coderabbitai"}, cls_gate, "", _DT_NOW)
		is True
	)


def test_every_page_of_open_prs_is_examined(cls_retry: ModuleType) -> None:
	"""A rate-limited PR on page two must be reachable, not silently dropped.

	``--paginate --slurp`` returns a list of PAGES, so the flattening is one level deeper than
	it looks. The obvious one-level comprehension iterates pages and yields nothing, and a
	janitor that examines nothing reports "checked 0" rather than failing — a silent partial
	pass, which is the failure this family of scripts exists to prevent.

	Parameters
	----------
	cls_retry : types.ModuleType
		The retry module.
	"""
	list_pages = [
		[{"number": 1}, {"number": 2}],
		[{"number": 3}],
	]

	assert cls_retry.flatten_pr_numbers(list_pages) == [1, 2, 3]


def test_a_malformed_page_cannot_crash_the_sweep(cls_retry: ModuleType) -> None:
	"""A page that is not a list, or an entry without a number, is skipped rather than fatal.

	This runs unattended every ten minutes, so one odd payload must not stop the PRs behind it
	from being examined.

	Parameters
	----------
	cls_retry : types.ModuleType
		The retry module.
	"""
	list_pages = [[{"number": 1}], "not-a-page", [{"no_number": True}, {"number": 4}]]

	assert cls_retry.flatten_pr_numbers(list_pages) == [1, 4]


def test_an_author_less_marker_cannot_match_an_unknown_identity(
	cls_retry: ModuleType, cls_gate: ModuleType
) -> None:
	"""An empty author must not equal an empty self-login — found by a SURVIVING mutant.

	Deleting the ``if not str_self`` guard changed nothing red, which is a gap report rather
	than proof the guard is redundant. Probing it showed the guard is load-bearing in exactly
	one shape: when our identity is unknown (``""``) and a comment carries an empty author
	(``""``), the author comparison MATCHES and an author-less marker suppresses the retry —
	the silent failure this file has now hit twice, in a third disguise.

	Two empty strings comparing equal is the kind of accident no reading catches and every
	mutation does, provided the suite contains the shape.

	Parameters
	----------
	cls_retry : types.ModuleType
		The retry module.
	cls_gate : types.ModuleType
		The gate module.
	"""
	list_comments = [
		_comment("coderabbitai", _STR_RATE_LIMITED, int_min_ago=6),
		_comment("", cls_retry._STR_REQUEST, int_min_ago=1),
	]
	dict_pr = _pr(list_comments, [])

	assert (
		cls_retry.pr_needs_retry(dict_pr, list_comments, {"coderabbitai"}, cls_gate, "", _DT_NOW)
		is True
	)


def test_one_unreadable_pr_does_not_end_the_sweep(
	cls_retry: ModuleType, cls_gate: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
	"""A PR whose fetch raises is skipped with a warning; the sweep continues.

	``fetch_pull_request`` raises on an API failure and indexes a node that can be null, so a
	single deleted, transferred or transiently-failing PR would abort the loop and leave every
	PR behind it unexamined — silently, because the run would simply end. This job runs
	unattended every ten minutes, so it must degrade per PR, never per sweep.

	Parameters
	----------
	cls_retry : types.ModuleType
		The retry module.
	cls_gate : types.ModuleType
		The gate module.
	monkeypatch : pytest.MonkeyPatch
		Fixture used to make the fetch raise.
	"""

	def _raise(*args: object, **kwargs: object) -> dict:
		raise RuntimeError("GraphQL query failed: boom")

	monkeypatch.setattr(cls_gate, "fetch_pull_request", _raise)

	assert (
		cls_retry.examine_pr("acme/widget", 7, {"coderabbitai"}, cls_gate, "guilhermegor") is False
	)
