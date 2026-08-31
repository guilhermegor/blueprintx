"""Unit tests for the assertion-weakening gate (offline; no git, no network).

**The negative control is the point** (blueprintx#324). A gate that claims to catch a PR
turning a red test green by weakening its assertion is worthless unless something in this
suite actually FAILS it. Every test below either proves a rule FIRES on the exact shape the
issue names, or pins a measured reason it must NOT fire — the should-fail witnesses from the
issue body, plus the literal-ish narrowing that measurement against real history required
(a rewritten left-hand expression, e.g. ``dict_calls["n"]`` -> ``cls_call.call_count``, on an
unchanged RHS constant must not be read as an edited expected value).
"""

import importlib.util
from pathlib import Path
import sys
from types import ModuleType

import pytest


_BIN = Path(__file__).resolve().parents[2] / "bin"


def _load(str_name: str) -> ModuleType:
	"""Load a ``bin/`` script by path (``bin/`` is not a package).

	Parameters
	----------
	str_name : str
		Module stem under ``bin/``.

	Returns
	-------
	ModuleType
		The imported module.
	"""
	cls_spec = importlib.util.spec_from_file_location(str_name, _BIN / f"{str_name}.py")
	cls_module = importlib.util.module_from_spec(cls_spec)
	sys.modules[str_name] = cls_module
	cls_spec.loader.exec_module(cls_module)
	return cls_module


gate = _load("check_assertion_weakening")


def _findings(str_old: str, str_new: str, *, bool_prod_changed: bool = False) -> list[str]:
	"""Run the file-level comparator over two versions of one test file's source.

	Parameters
	----------
	str_old : str
		Content at the merge-base.
	str_new : str
		Content in this change.
	bool_prod_changed : bool
		Whether a non-test file also changed in this diff.

	Returns
	-------
	list of str
		Findings from ``gate._file_findings``.
	"""
	return gate._file_findings("tests/unit/test_sample.py", str_old, str_new, bool_prod_changed)


# --------------------------
# Deletion — a test or a whole file disappearing
# --------------------------


def test_a_deleted_test_function_is_reported() -> None:
	"""A test present at the merge-base but absent now is a finding."""
	str_old = "def test_x() -> None:\n\tassert 1 == 1\n"
	str_new = "def test_other() -> None:\n\tassert 1 == 1\n"

	list_problems = _findings(str_old, str_new)

	assert len(list_problems) == 1
	assert "test_x" in list_problems[0]
	assert "deleted" in list_problems[0]


def test_an_unrelated_new_test_alongside_the_old_one_is_clean() -> None:
	"""Adding a sibling test while keeping the original one intact is not a finding."""
	str_old = "def test_x() -> None:\n\tassert 1 == 1\n"
	str_new = (
		"def test_x() -> None:\n\tassert 1 == 1\n\n\ndef test_y() -> None:\n\tassert 2 == 2\n"
	)

	assert _findings(str_old, str_new) == []


# --------------------------
# 🔴 The negative control — assertion count reduced
# --------------------------


def test_an_assertion_removed_is_reported() -> None:
	"""A test that had two assertions and now has one is a finding, count-based."""
	str_old = "def test_x() -> None:\n\tassert 1 == 1\n\tassert 2 == 2\n"
	str_new = "def test_x() -> None:\n\tassert 1 == 1\n"

	list_problems = _findings(str_old, str_new)

	assert len(list_problems) == 1
	assert "test_x" in list_problems[0]
	assert "lost 1 assertion" in list_problems[0]


def test_trivialised_to_assert_true_is_reported() -> None:
	"""A real assertion collapsed to a bare truthy constant is a finding."""
	str_old = "def test_x() -> None:\n\tassert compute() == 5\n"
	str_new = "def test_x() -> None:\n\tassert True\n"

	list_problems = _findings(str_old, str_new)

	assert any("trivialised" in str_p for str_p in list_problems)


# --------------------------
# Operator weakened — blueprintx#289's live example
# --------------------------


def test_equality_weakened_to_membership_is_reported() -> None:
	"""``==`` narrowed to ``in`` is exactly the defect blueprintx#289's review caught."""
	str_old = 'def test_x() -> None:\n\tassert resolve_intent(x) == "send"\n'
	str_new = 'def test_x() -> None:\n\tassert resolve_intent(x) in {"send", "reconcile"}\n'

	list_problems = _findings(str_old, str_new)

	assert len(list_problems) == 1
	assert "operator weakened from == to in" in list_problems[0]
	assert "line 2" in list_problems[0]


def test_a_stricter_operator_swap_is_not_flagged() -> None:
	"""``==`` tightened to a strict inequality is out of the decidable core, by design."""
	str_old = "def test_x() -> None:\n\tassert compute() == 5\n"
	str_new = "def test_x() -> None:\n\tassert compute() > 5\n"

	assert _findings(str_old, str_new) == []


# --------------------------
# unittest-style call weakened
# --------------------------


def test_assert_equal_weakened_to_assert_true_is_reported() -> None:
	"""``assertEqual`` downgraded to ``assertTrue`` loses the value it pinned."""
	str_old = "class T:\n\tdef test_x(self) -> None:\n\t\tself.assertEqual(compute(), 5)\n"
	str_new = "class T:\n\tdef test_x(self) -> None:\n\t\tself.assertTrue(compute())\n"

	list_problems = _findings(str_old, str_new)

	assert any("assertEqual() weakened to assertTrue()" in str_p for str_p in list_problems)


# --------------------------
# pytest.raises broadened
# --------------------------


def test_raises_broadened_to_bare_exception_is_reported() -> None:
	"""A specific exception type widened to ``Exception`` loses what it pinned."""
	str_old = "def test_x() -> None:\n\twith pytest.raises(ValueError):\n\t\tf()\n"
	str_new = "def test_x() -> None:\n\twith pytest.raises(Exception):\n\t\tf()\n"

	list_problems = _findings(str_old, str_new)

	str_want = "pytest.raises broadened from ValueError to Exception"
	assert any(str_want in str_p for str_p in list_problems)


def test_raises_replaced_in_place_by_a_plain_assertion_is_reported() -> None:
	"""Dropping the ``raises`` context while keeping the check count is a finding.

	Padded with a second, unchanged assertion on both sides so the two checks stay
	POSITIONALLY paired — otherwise the count-based rule fires first, and this test would
	prove that rule instead of the raises-specific one it targets.
	"""
	str_old = (
		"def test_x() -> None:\n\twith pytest.raises(ValueError):\n\t\tf()\n\tassert 1 == 1\n"
	)
	str_new = "def test_x() -> None:\n\tassert True\n\tassert 1 == 1\n"

	list_problems = _findings(str_old, str_new)

	assert any("pytest.raises removed" in str_p for str_p in list_problems)


def test_raises_kept_at_the_same_specificity_is_clean() -> None:
	"""An unrelated line added around an unchanged ``raises`` block is not a finding."""
	str_old = "def test_x() -> None:\n\twith pytest.raises(ValueError):\n\t\tf()\n"
	str_new = "def test_x() -> None:\n\tprepare()\n\twith pytest.raises(ValueError):\n\t\tf()\n"

	assert _findings(str_old, str_new) == []


# --------------------------
# skip/xfail newly added
# --------------------------


def test_a_newly_added_skip_marker_is_reported() -> None:
	"""A test that gained ``@pytest.mark.skip`` without carrying it before is a finding."""
	str_old = "def test_x() -> None:\n\tassert 1 == 1\n"
	str_new = "@pytest.mark.skip(reason='flaky')\ndef test_x() -> None:\n\tassert 1 == 1\n"

	list_problems = _findings(str_old, str_new)

	assert any("newly marked skip" in str_p for str_p in list_problems)


# --------------------------
# Expected value changed — gated on production code also changing
# --------------------------


def test_expected_value_changed_alongside_production_code_is_reported() -> None:
	"""The exact blueprintx#323 shape: a literal expectation edited, code changed too."""
	str_old = 'def test_x() -> None:\n\tassert to_decimal_strict("1.999", 2) == Decimal("1.99")\n'
	str_new = 'def test_x() -> None:\n\tassert to_decimal_strict("1.999", 2) == Decimal("2.00")\n'

	list_problems = _findings(str_old, str_new, bool_prod_changed=True)

	assert len(list_problems) == 1
	assert "expected value changed while production code changed" in list_problems[0]


def test_expected_value_changed_without_production_code_changing_is_clean() -> None:
	"""Should-fail witness #3: a test-only correction must PASS, never be caught."""
	str_old = 'def test_x() -> None:\n\tassert to_decimal_strict("1.999", 2) == Decimal("1.99")\n'
	str_new = 'def test_x() -> None:\n\tassert to_decimal_strict("1.999", 2) == Decimal("2.00")\n'

	assert _findings(str_old, str_new, bool_prod_changed=False) == []


def test_a_rewritten_left_hand_expression_is_not_read_as_a_changed_value() -> None:
	"""Measured false positive against real history, narrowed away (blueprintx#324's PR body).

	A rewrite from a counter dict to a Mock's call-count attribute
	(``dict_calls["n"]`` -> ``cls_call.call_count``) leaves the RHS literal ``1`` untouched.
	Neither changed side is literal-ish (a Subscript, an Attribute), so this reads as the
	rewrite it is, not an edited expectation — measured on blueprintx's own
	``test_retry.py`` history.
	"""
	str_old = 'def test_x() -> None:\n\tassert dict_calls["n"] == 1\n'
	str_new = "def test_x() -> None:\n\tassert cls_call.call_count == 1\n"

	assert _findings(str_old, str_new, bool_prod_changed=True) == []


# --------------------------
# Three states: flagged / clean / could not parse
# --------------------------


def test_an_unparsable_new_version_is_a_finding_not_a_silent_pass() -> None:
	"""A file the gate cannot parse must FAIL, never read as clean.

	Mirrors #324's sibling gates: "cannot be checked" and "is clean" are opposite facts.
	"""
	str_old = "def test_x() -> None:\n\tassert 1 == 1\n"
	str_new = "def test_x(:\n"

	list_problems = _findings(str_old, str_new)

	assert len(list_problems) == 1
	assert "could not parse" in list_problems[0]


def test_a_clean_file_with_no_test_changes_reports_nothing() -> None:
	"""Whitespace/comment-only edits with no assertion-shape change produce zero findings."""
	str_old = "def test_x() -> None:\n\tassert 1 == 1\n"
	str_new = "def test_x() -> None:\n\t# a harmless comment\n\tassert 1 == 1\n"

	assert _findings(str_old, str_new) == []


# --------------------------
# The escape hatch
# --------------------------


def test_the_report_passes_a_flagged_diff_with_a_justification_trailer(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""``test-change-ok: <reason>`` in the searched text clears an otherwise-failing report.

	Parameters
	----------
	monkeypatch : pytest.MonkeyPatch
		Replaces the gate's git runner so the trailer search reads a fixed commit message.
	"""
	monkeypatch.setattr(
		gate,
		"_git",
		lambda _args: "fix: correct the truncation bug\n\n"
		"test-change-ok: fixing the ROUND_DOWN bug this test pins\n",
	)

	assert gate.report(["some finding"], "base-sha", 1) == 0


def test_the_report_fails_a_flagged_diff_with_no_justification(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""No ``test-change-ok`` trailer anywhere means the weakening blocks the PR."""
	monkeypatch.setattr(gate, "_git", lambda _args: "fix: unrelated commit body\n")

	assert gate.report(["some finding"], "base-sha", 1) == 1


def test_a_bare_marker_with_no_reason_does_not_justify(monkeypatch: pytest.MonkeyPatch) -> None:
	"""The reason is REQUIRED, matching ``gate-change-ok:``'s convention."""
	monkeypatch.setattr(gate, "_git", lambda _args: "test-change-ok:\n")

	assert gate.report(["some finding"], "base-sha", 1) == 1


def test_two_classes_sharing_a_method_name_are_tracked_separately() -> None:
	"""A bare method name is not identity: two classes routinely define ``test_value``.

	Keying only on ``node.name`` let the later class overwrite the earlier one, so weakening
	the overwritten method produced no finding at all — a silent miss, and the worst kind for
	a gate whose whole job is to notice a check that got weaker.
	"""
	str_old = (
		'class TestOne:\n\tdef test_v(self) -> None:\n\t\tassert a() == "send"\n\n\n'
		'class TestTwo:\n\tdef test_v(self) -> None:\n\t\tassert b() == "x"\n'
	)
	str_new = (
		'class TestOne:\n\tdef test_v(self) -> None:\n\t\tassert a() in {"send", "recon"}\n\n\n'
		'class TestTwo:\n\tdef test_v(self) -> None:\n\t\tassert b() == "x"\n'
	)
	list_found = _findings(str_old, str_new)
	assert len(list_found) == 1
	assert "TestOne.test_v" in list_found[0]


def test_a_unittest_call_rewritten_as_a_weaker_bare_assert_is_reported() -> None:
	"""Changing the assertion's KIND must not hide the weakening.

	``self.assertEqual(a, b)`` rewritten as ``assert a in b`` keeps the check count identical,
	so a same-kind comparison never sees it. The call is normalised to the operator it is
	equivalent to before the pair is compared.
	"""
	str_old = 'class T:\n\tdef test_v(self) -> None:\n\t\tself.assertEqual(a(), "send")\n'
	str_new = 'class T:\n\tdef test_v(self) -> None:\n\t\tassert a() in {"send", "recon"}\n'
	list_found = _findings(str_old, str_new)
	assert len(list_found) == 1
	assert "in" in list_found[0]


def test_a_unittest_call_rewritten_as_an_equivalent_bare_assert_is_clean() -> None:
	"""⚠️ The other direction: the cross-kind rule must not fire on an ordinary refactor.

	Dropping ``unittest`` for a bare ``assert`` with the SAME operator asserts exactly as much.
	Without this case the rule above would also be satisfied by one that flags every rewrite,
	which is how a gate earns its way into everyone's escape hatch.
	"""
	str_old = 'class T:\n\tdef test_v(self) -> None:\n\t\tself.assertEqual(a(), "send")\n'
	str_new = 'class T:\n\tdef test_v(self) -> None:\n\t\tassert a() == "send"\n'
	assert _findings(str_old, str_new) == []


def test_a_unittest_call_rewritten_as_a_stricter_bare_assert_is_clean() -> None:
	"""A stricter operator after the rewrite is a strengthening, not a weakening."""
	str_old = "class T:\n\tdef test_v(self) -> None:\n\t\tself.assertEqual(a(), 5)\n"
	str_new = "class T:\n\tdef test_v(self) -> None:\n\t\tassert a() > 5\n"
	assert _findings(str_old, str_new) == []


@pytest.mark.parametrize("str_new_assert", ["assert True", "assert 1", 'assert "x"'])
def test_a_call_trivialised_to_any_truthy_constant_is_reported(str_new_assert: str) -> None:
	"""``assert True`` is not the only assertion that can never fail.

	The cross-kind rule first checked ``value is True`` literally, so ``assert 1`` and
	``assert "x"`` — equally unfailable — slipped through. It now reuses
	``_is_trivial_assert_test()``, the same predicate the same-kind path already used, rather
	than carrying a second, narrower notion of "trivial".

	Parameters
	----------
	str_new_assert : str
		The trivialised assertion replacing the unittest call.
	"""
	str_old = "class T:\n\tdef test_v(self) -> None:\n\t\tself.assertEqual(a(), 5)\n"
	str_new = f"class T:\n\tdef test_v(self) -> None:\n\t\t{str_new_assert}\n"
	list_found = _findings(str_old, str_new)
	assert len(list_found) == 1
	assert "truthy constant" in list_found[0]


@pytest.mark.parametrize("str_new_assert", ["assert 0", "assert None"])
def test_a_call_replaced_by_a_falsy_constant_is_not_a_weakening(str_new_assert: str) -> None:
	"""⚠️ The other direction: a falsy constant always FAILS, so it is not weaker.

	Without this case the rule above would also be satisfied by one that flags every constant,
	which would fire on a test deliberately pinned red — and a gate that cannot tell those
	apart gets an escape hatch instead of a fix.

	Parameters
	----------
	str_new_assert : str
		The falsy assertion replacing the unittest call.
	"""
	str_old = "class T:\n\tdef test_v(self) -> None:\n\t\tself.assertEqual(a(), 5)\n"
	str_new = f"class T:\n\tdef test_v(self) -> None:\n\t\t{str_new_assert}\n"
	assert _findings(str_old, str_new) == []
