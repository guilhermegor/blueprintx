"""Unit tests for the PR quality gate's classifier (pure, offline, no network).

Everything above ``main()`` in ``bin/pr_gate.py`` is a pure function precisely so the whole
classification policy is testable with no API access — the autouse network guard in
``tests/conftest.py`` would block a real call anyway.

``bin/`` is not a package, so the module is loaded **by path** via importlib.
"""

import importlib.util
from pathlib import Path
import sys
from types import ModuleType

import pytest


_GATE_PATH = Path(__file__).resolve().parents[2] / "bin" / "pr_gate.py"


def _load_gate() -> ModuleType:
	"""Load ``bin/pr_gate.py`` as a module by path.

	Returns
	-------
	ModuleType
		The imported ``pr_gate`` module.
	"""
	cls_spec = importlib.util.spec_from_file_location("pr_gate", _GATE_PATH)
	cls_module = importlib.util.module_from_spec(cls_spec)
	sys.modules["pr_gate"] = cls_module
	cls_spec.loader.exec_module(cls_module)
	return cls_module


gate = _load_gate()


@pytest.mark.parametrize(
	("str_path", "str_expected"),
	[
		("src/model/loader.py", "src"),
		("tests/unit/test_x.py", "tests"),
		(".github/workflows/tests.yaml", "ci"),
		("bin/venv.sh", "ci"),
		("pyproject.toml", "deps"),
		("poetry.lock", "deps"),
		("docs/usage.md", "docs"),
		("mkdocs.yml", "docs"),
		("some/unknown/thing.xyz", "other"),
	],
)
def test_classify_path_maps_each_class(str_path: str, str_expected: str) -> None:
	"""Each representative path lands in its documented risk class."""
	assert gate.classify_path(str_path) == str_expected


def test_classify_risk_returns_the_most_dangerous_class() -> None:
	"""A mixed PR collapses to its most dangerous class — docs never masks src."""
	assert gate.classify_risk(["docs/a.md", "src/x.py"]) == "src"
	assert gate.classify_risk(["docs/a.md", "tests/test_x.py"]) == "tests"


def test_classify_risk_treats_an_unknown_path_as_unsafe() -> None:
	"""An unmatched path outranks the safe classes: unknown is unsafe (default-deny)."""
	assert gate.classify_risk(["docs/a.md", "weird.bin"]) == "other"
	assert gate.classify_risk(["weird.bin"]) not in gate.AUTO_MERGEABLE


@pytest.mark.parametrize(
	("int_lines", "str_bucket"),
	[
		(0, "XS"),
		(10, "XS"),
		(11, "S"),
		(50, "S"),
		(51, "M"),
		(200, "M"),
		(201, "L"),
		(500, "L"),
		(501, "XL"),
	],
)
def test_classify_size_buckets(int_lines: int, str_bucket: str) -> None:
	"""Changed-line counts fall in the documented buckets, boundaries included."""
	assert gate.classify_size(int_lines) == str_bucket


def test_is_lockfile_only_is_narrow() -> None:
	"""Only a lockfile-ONLY diff qualifies — a hand-edited sibling must not."""
	assert gate.is_lockfile_only([gate.LOCKFILE]) is True
	assert gate.is_lockfile_only([gate.LOCKFILE, "pyproject.toml"]) is False
	assert gate.is_lockfile_only(["pyproject.toml"]) is False


# ⚠️ parametrize, not a `for` in the body. A loop asserts N cases behind ONE green: the report
# cannot say which risk class was checked, and the first failure hides the rest. tests/ is capped
# at complexity 1 (bin/check_complexity.sh), which is this rule made mechanical.
@pytest.mark.parametrize("str_risk", sorted(gate.AUTO_MERGEABLE))
def test_auto_merge_allows_safe_classes_without_a_label(str_risk: str) -> None:
	"""Consent is opt-OUT: the safe classes merge with no label at all."""
	assert gate.is_auto_mergeable(str_risk, "M", []) is True


@pytest.mark.parametrize("str_risk", ["src", "tests", "other"])
def test_auto_merge_refuses_dangerous_classes(str_risk: str) -> None:
	"""src/tests define what 'passing' means; other is unknown — none may auto-merge."""
	assert gate.is_auto_mergeable(str_risk, "XS", []) is False


def test_block_label_is_the_opt_out() -> None:
	"""The do-not-merge label vetoes an otherwise-eligible PR."""
	assert gate.is_auto_mergeable("docs", "S", [gate.BLOCK_LABEL]) is False


def test_xl_veto_applies_to_handwritten_but_is_waived_for_a_lockfile() -> None:
	"""A huge hand-written diff is vetoed; a regenerated lockfile is exempt.

	The regression this guards: a lockfile's diff size tracks how many dependency hashes moved,
	not how much risk arrived — so without the exemption, whether the weekly bump self-merges
	depends on how many packages happened to move that week.
	"""
	assert gate.is_auto_mergeable("deps", "XL", []) is False
	assert gate.is_auto_mergeable("deps", "XL", [], bool_lockfile_only=True) is True


def test_gate_state_lets_red_outrank_pending() -> None:
	"""For DISPLAY, a known failure outranks a still-deciding axis."""
	assert gate.gate_state({"a": "failure", "b": "pending"}) == "failure"
	assert gate.gate_state({"a": "pending", "b": "success"}) == "pending"
	assert gate.gate_state({"a": "success"}) == "success"


def test_terminality_is_separate_from_display_state() -> None:
	"""A red-with-pending set is NOT terminal — conflating the two freezes the sticky comment.

	Breaking the poll loop on ``gate_state() != 'pending'`` would stop on the first transient red
	while other checks still run, and nothing re-renders the comment afterwards.
	"""
	dict_axes = {"a": "failure", "b": "pending"}
	assert gate.gate_state(dict_axes) == "failure"
	assert gate.axes_are_terminal(dict_axes) is False
	assert gate.axes_are_terminal({"a": "failure", "b": "success"}) is True


def test_axis_with_no_check_run_is_pending_not_failing() -> None:
	"""An axis with no check-run yet on this head SHA is awaiting a result, never a failure."""
	dict_axes, _ = gate.collect_axes([], {"tests": ("Run Automated Tests",)})
	assert dict_axes["tests"] == "pending"


def test_collect_axes_matches_the_analysis_not_the_umbrella() -> None:
	"""CodeQL's umbrella check must not decide the axis — the Analyze runs carry the conclusion."""
	list_runs = [
		{"name": "CodeQL", "status": "in_progress", "conclusion": None},
		{"name": "Analyze (python)", "status": "completed", "conclusion": "success"},
	]
	dict_axes, _ = gate.collect_axes(list_runs, {"code scanning": ("Analyze",)})
	assert dict_axes["code scanning"] == "success"


def test_failing_axis_names_its_checks() -> None:
	"""A failing axis reports WHICH checks failed — a bare count teaches the reader nothing."""
	list_runs = [
		{"name": "Run Automated Tests (ubuntu)", "status": "completed", "conclusion": "failure"}
	]
	dict_axes, dict_failing = gate.collect_axes(list_runs, {"tests": ("Run Automated Tests",)})
	assert dict_axes["tests"] == "failure"
	assert dict_failing["tests"] == ["Run Automated Tests (ubuntu)"]


def test_render_comment_carries_the_sticky_marker_and_the_failing_names() -> None:
	"""The rendered body carries the hidden marker (so it updates in place) and names failures."""
	str_body = gate.render_comment(
		"deps", "L", {"tests": "failure"}, False, {"tests": ["Run Automated Tests (ubuntu)"]}
	)
	assert gate.COMMENT_MARKER in str_body
	assert "Run Automated Tests (ubuntu)" in str_body
	assert "risk:" in str_body
	assert "deps" in str_body


def test_graphql_reports_a_refused_mutation_to_stderr(
	capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
	"""A GraphQL refusal is HTTP 200 + an ``errors`` body — it must not be discarded in silence.

	Regression for the defect where the mutation's return value was thrown away: a rejected
	auto-merge looked identical to a successful one in the log.
	"""
	monkeypatch.setattr(gate, "_api", lambda *a, **k: {"errors": [{"message": "refused"}]})
	gate._graphql("mutation{}", {})
	assert "refused" in capsys.readouterr().err


def test_graphql_stays_quiet_on_a_clean_response(
	capsys: pytest.CaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
	"""A response with no ``errors`` key prints nothing — the check must not cry wolf."""
	monkeypatch.setattr(gate, "_api", lambda *a, **k: {"data": {"clientMutationId": None}})
	gate._graphql("mutation{}", {})
	assert capsys.readouterr().err == ""


# --------------------------
# Module Utilities
# --------------------------
# Plain module-level helpers, never nested inside a test — a nested `def` counts as a decision
# point for ruff's C901, and tests/ is capped at complexity 1 (see bin/check_complexity.sh).

_DICT_MAIN_API_RESPONSES = {
	"https://api.github.com/repos/o/r/pulls/7": {
		"head": {"sha": "sha1"},
		"additions": 2,
		"deletions": 0,
		"labels": [],
		"node_id": "PR_NODE",
	},
	"https://api.github.com/repos/o/r/pulls/7/files?per_page=100": [
		{"filename": "docs/readme.md"}
	],
	"https://api.github.com/repos/o/r/issues/7/comments": [],
}


def _fake_api_for_main(str_method: str, str_url: str, dict_payload: dict | None = None) -> object:
	"""Stand in for every REST call ``main()`` makes, keyed by URL.

	Parameters
	----------
	str_method : str
		HTTP method (ignored — the fake distinguishes calls by URL only).
	str_url : str
		Absolute URL requested.
	dict_payload : dict, optional
		JSON body (ignored).

	Returns
	-------
	object
		The canned response for ``str_url``, or ``None`` when unmapped.
	"""
	return _DICT_MAIN_API_RESPONSES.get(str_url)


class _CallRecorder:
	"""Record that this seam was invoked, standing in for either of two `main()` calls.

	Both `poll_axes_until_terminal` (destructured as ``dict_axes, dict_failing``) and
	`_enable_auto_merge` (return value discarded) accept the same ``({}, {})`` shape, so one
	recorder type replaces either seam with no branch on which one it is.
	"""

	def __init__(self, list_target: list, str_label: str) -> None:
		"""Bind the shared call log and this instance's label.

		Parameters
		----------
		list_target : list
			The call log every recorder instance appends its label to, in call order.
		str_label : str
			The label this instance appends when invoked.
		"""
		self._list_target = list_target
		self._str_label = str_label

	def __call__(self, *args: object, **kwargs: object) -> tuple[dict, dict]:
		"""Append this recorder's label and return the shared stand-in value.

		Parameters
		----------
		*args : object
			Ignored positional arguments from the real seam's call site.
		**kwargs : object
			Ignored keyword arguments from the real seam's call site.

		Returns
		-------
		tuple of dict
			``({}, {})`` — valid whether the caller destructures it or discards it.
		"""
		self._list_target.append(self._str_label)
		return {}, {}


# --------------------------
# Tests
# --------------------------


def test_main_hands_the_merge_over_after_the_poll_not_before(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""The merge handover happens AFTER polling, never up front.

	Arming ``enablePullRequestAutoMerge`` at ``opened`` finds nothing pending yet (sibling
	check-runs have not registered), so GitHub either merges too early or refuses the mutation
	outright. Polling first gives those check-runs time to register.
	"""
	monkeypatch.setenv("GITHUB_TOKEN", "tkn")
	monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
	monkeypatch.setenv("PR_NUMBER", "7")
	list_calls: list = []

	monkeypatch.setattr(gate, "_api", _fake_api_for_main)
	monkeypatch.setattr(gate, "poll_axes_until_terminal", _CallRecorder(list_calls, "poll"))
	monkeypatch.setattr(gate, "_enable_auto_merge", _CallRecorder(list_calls, "enable_auto_merge"))

	gate.main()

	assert list_calls == ["poll", "enable_auto_merge"]
