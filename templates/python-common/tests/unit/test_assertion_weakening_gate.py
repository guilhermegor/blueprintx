"""Unit tests for the assertion-weakening gate (offline; no git, no network).

**The negative control is the point** (blueprintx#324). A gate that claims to catch a PR
turning a red test green by weakening its assertion is worthless unless something in this
suite actually FAILS it. Every test below either proves a rule FIRES on the exact shape the
issue names, or pins a measured reason it must NOT fire — the should-fail witnesses from the
issue body, plus the literal-ish narrowing that measurement against real history required
(a rewritten left-hand expression, e.g. ``dict_calls["n"]`` -> ``cls_call.call_count``, on an
unchanged RHS constant must not be read as an edited expected value).
"""

import ast
from functools import partial
import importlib.util
from pathlib import Path
import subprocess
import sys
from types import ModuleType
from unittest.mock import MagicMock

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


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Start every test from a local pre-commit shell with no ``TEST_CHANGE_OK`` and no CI marker.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Removes the CI markers, the hatch variable and the event path from the shell.
    """
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("TEST_CHANGE_OK", raising=False)
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)
    monkeypatch.setenv("PRE_COMMIT", "1")
    monkeypatch.setattr(sys.modules["gate_env"], "has_terminal", lambda: True)


def _findings(str_old: str, *, str_new: str, bool_prod_changed: bool = False) -> list[str]:
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
    return gate._file_findings(
        "tests/unit/test_sample.py",
        str_old_text=str_old,
        str_new_text=str_new,
        bool_prod_changed=bool_prod_changed,
    )


def _sole_finding(str_old: str, *, str_new: str, bool_prod_changed: bool = False) -> str:
    """Run the comparator and return its single finding, asserting there is exactly one.

    Every fixture in this file is a two-line diff built to trip exactly one rule, so "one
    finding, not a cascade" is a precondition of the fixture rather than a per-test
    behaviour (blueprintx#544). Hoisting it here keeps each test at one assertion AND makes
    every caller check the count, including those that previously only indexed ``[0]``.

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
    str
        The one finding.
    """
    list_problems = _findings(str_old, str_new=str_new, bool_prod_changed=bool_prod_changed)
    assert len(list_problems) == 1, list_problems
    return list_problems[0]


@pytest.mark.parametrize("str_fragment", ["test_x", "deleted"])
def test_a_deleted_test_function_is_reported(str_fragment: str) -> None:
    """A test present at the merge-base but absent now is a finding."""
    assert str_fragment in _sole_finding(
        "def test_x() -> None:\n\tassert 1 == 1\n",
        str_new="def test_other() -> None:\n\tassert 1 == 1\n",
    )


def test_a_renamed_test_with_the_same_assertions_is_clean() -> None:
    """Renaming ``..._six_...`` to ``..._seven_...`` is not a deletion (#1073)."""
    str_old = "def test_has_six_required_pages() -> None:\n\tassert 1 == 1\n"
    str_new = "def test_has_seven_required_pages() -> None:\n\tassert 1 == 1\n"
    assert _findings(str_old, str_new=str_new) == []


def test_a_renamed_test_that_lost_an_assertion_is_still_reported() -> None:
    """NEGATIVE CONTROL: a rename does not launder a weakened body."""
    str_old = "def test_has_six_required_pages() -> None:\n\tassert 1 == 1\n\tassert 2 == 2\n"
    str_new = "def test_has_seven_required_pages() -> None:\n\tassert 1 == 1\n"
    assert "lost 1 assertion" in _sole_finding(str_old, str_new=str_new)


def test_an_unrelated_new_test_alongside_the_old_one_is_clean() -> None:
    """Adding a sibling test while keeping the original one intact is not a finding."""
    str_old = "def test_x() -> None:\n\tassert 1 == 1\n"
    str_new = (
        "def test_x() -> None:\n\tassert 1 == 1\n\n\ndef test_y() -> None:\n\tassert 2 == 2\n"
    )

    assert _findings(str_old, str_new=str_new) == []


@pytest.mark.parametrize("str_fragment", ["test_x", "lost 1 assertion"])
def test_an_assertion_removed_is_reported(str_fragment: str) -> None:
    """A test that had two assertions and now has one is a finding, count-based."""
    assert str_fragment in _sole_finding(
        "def test_x() -> None:\n\tassert 1 == 1\n\tassert 2 == 2\n",
        str_new="def test_x() -> None:\n\tassert 1 == 1\n",
    )


def test_trivialised_to_assert_true_is_reported() -> None:
    """A real assertion collapsed to a bare truthy constant is a finding."""
    str_old = "def test_x() -> None:\n\tassert compute() == 5\n"
    str_new = "def test_x() -> None:\n\tassert True\n"

    list_problems = _findings(str_old, str_new=str_new)

    assert any("trivialised" in str_p for str_p in list_problems)


@pytest.mark.parametrize("str_fragment", ["operator weakened from == to in", "line 2"])
def test_equality_weakened_to_membership_is_reported(str_fragment: str) -> None:
    """``==`` narrowed to ``in`` is exactly the defect blueprintx#289's review caught."""
    assert str_fragment in _sole_finding(
        'def test_x() -> None:\n\tassert resolve_intent(x) == "send"\n',
        str_new='def test_x() -> None:\n\tassert resolve_intent(x) in {"send", "reconcile"}\n',
    )


@pytest.mark.parametrize(
    ("str_symbol", "str_fragment"),
    [
        (">", "operator weakened from == to >"),
        ("<", "operator weakened from == to <"),
        (">=", "operator weakened from == to >="),
        ("<=", "operator weakened from == to <="),
    ],
)
def test_equality_loosened_to_an_inequality_is_reported(
    str_symbol: str, *, str_fragment: str
) -> None:
    """``x == 5`` does not imply ``x > 5``: any inequality accepts values the equality rejected."""
    assert str_fragment in _sole_finding(
        "def test_x() -> None:\n\tassert compute() == 5\n",
        str_new=f"def test_x() -> None:\n\tassert compute() {str_symbol} 5\n",
    )


@pytest.mark.parametrize("str_symbol", [">", "<"])
def test_equality_loosened_to_an_inequality_in_a_call_rewrite_is_reported(
    str_symbol: str,
) -> None:
    """``self.assertEqual(a, b)`` rewritten as a bare ``a > b`` is the same loosening."""
    assert "weakened to a bare assert with " + str_symbol in _sole_finding(
        "class T:\n\tdef test_x(self) -> None:\n\t\tself.assertEqual(compute(), 5)\n",
        str_new=f"class T:\n\tdef test_x(self) -> None:\n\t\tassert compute() {str_symbol} 5\n",
    )


@pytest.mark.parametrize("str_symbol", [">", "<"])
def test_an_assert_that_was_always_an_inequality_is_clean(str_symbol: str) -> None:
    """The gate judges a CHANGE from ``==``, so a pre-existing inequality is untouched."""
    str_src = f"def test_x() -> None:\n\tassert compute() {str_symbol} 5\n"

    assert _findings(str_src, str_new=str_src) == []


@pytest.mark.parametrize("str_symbol", [">", "<"])
def test_an_inequality_tightened_to_equality_is_clean(str_symbol: str) -> None:
    """Strengthening ``x > 5`` to ``x == 5`` pins more, not less, so it is not a finding."""
    assert (
        _findings(
            f"def test_x() -> None:\n\tassert compute() {str_symbol} 5\n",
            str_new="def test_x() -> None:\n\tassert compute() == 5\n",
        )
        == []
    )


@pytest.mark.parametrize(
    "str_call", ["assertGreater", "assertLess", "assertGreaterEqual", "assertLessEqual"]
)
def test_assert_equal_loosened_to_an_inequality_call_is_reported(str_call: str) -> None:
    """``assertEqual`` swapped for an inequality call is the unittest twin of ``== -> >``."""
    assert f"assertEqual() weakened to {str_call}()" in _sole_finding(
        "class T:\n\tdef test_x(self) -> None:\n\t\tself.assertEqual(compute(), 5)\n",
        str_new=f"class T:\n\tdef test_x(self) -> None:\n\t\tself.{str_call}(compute(), 5)\n",
    )


def test_assert_equal_weakened_to_assert_true_is_reported() -> None:
    """``assertEqual`` downgraded to ``assertTrue`` loses the value it pinned."""
    str_old = "class T:\n\tdef test_x(self) -> None:\n\t\tself.assertEqual(compute(), 5)\n"
    str_new = "class T:\n\tdef test_x(self) -> None:\n\t\tself.assertTrue(compute())\n"

    list_problems = _findings(str_old, str_new=str_new)

    assert any("assertEqual() weakened to assertTrue()" in str_p for str_p in list_problems)


def test_raises_broadened_to_bare_exception_is_reported() -> None:
    """A specific exception type widened to ``Exception`` loses what it pinned."""
    str_old = "def test_x() -> None:\n\twith pytest.raises(ValueError):\n\t\tf()\n"
    str_new = "def test_x() -> None:\n\twith pytest.raises(Exception):\n\t\tf()\n"

    list_problems = _findings(str_old, str_new=str_new)

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

    list_problems = _findings(str_old, str_new=str_new)

    assert any("pytest.raises removed" in str_p for str_p in list_problems)


def test_raises_kept_at_the_same_specificity_is_clean() -> None:
    """An unrelated line added around an unchanged ``raises`` block is not a finding."""
    str_old = "def test_x() -> None:\n\twith pytest.raises(ValueError):\n\t\tf()\n"
    str_new = "def test_x() -> None:\n\tprepare()\n\twith pytest.raises(ValueError):\n\t\tf()\n"

    assert _findings(str_old, str_new=str_new) == []


def test_a_newly_added_skip_marker_is_reported() -> None:
    """A test that gained ``@pytest.mark.skip`` without carrying it before is a finding."""
    str_old = "def test_x() -> None:\n\tassert 1 == 1\n"
    str_new = "@pytest.mark.skip(reason='flaky')\ndef test_x() -> None:\n\tassert 1 == 1\n"

    list_problems = _findings(str_old, str_new=str_new)

    assert any("newly marked skip" in str_p for str_p in list_problems)


def test_expected_value_changed_alongside_production_code_is_reported() -> None:
    """The exact blueprintx#323 shape: a literal expectation edited, code changed too."""
    str_old = 'def test_x() -> None:\n\tassert to_decimal_strict("1.999", 2) == Decimal("1.99")\n'
    str_new = 'def test_x() -> None:\n\tassert to_decimal_strict("1.999", 2) == Decimal("2.00")\n'

    assert "expected value changed while production code changed" in _sole_finding(
        str_old, str_new=str_new, bool_prod_changed=True
    )


def test_expected_value_changed_without_production_code_changing_is_clean() -> None:
    """Should-fail witness #3: a test-only correction must PASS, never be caught."""
    str_old = 'def test_x() -> None:\n\tassert to_decimal_strict("1.999", 2) == Decimal("1.99")\n'
    str_new = 'def test_x() -> None:\n\tassert to_decimal_strict("1.999", 2) == Decimal("2.00")\n'

    assert _findings(str_old, str_new=str_new, bool_prod_changed=False) == []


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

    assert _findings(str_old, str_new=str_new, bool_prod_changed=True) == []


def test_an_unparsable_new_version_is_a_finding_not_a_silent_pass() -> None:
    """A file the gate cannot parse must FAIL, never read as clean.

    Mirrors #324's sibling gates: "cannot be checked" and "is clean" are opposite facts.
    """
    assert "could not parse" in _sole_finding(
        "def test_x() -> None:\n\tassert 1 == 1\n", str_new="def test_x(:\n"
    )


def test_a_clean_file_with_no_test_changes_reports_nothing() -> None:
    """Whitespace/comment-only edits with no assertion-shape change produce zero findings."""
    str_old = "def test_x() -> None:\n\tassert 1 == 1\n"
    str_new = "def test_x() -> None:\n\t# a harmless comment\n\tassert 1 == 1\n"

    assert _findings(str_old, str_new=str_new) == []


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
        lambda _args: (
            "fix: correct the truncation bug\n\n"
            "test-change-ok: fixing the ROUND_DOWN bug this test pins\n"
        ),
    )

    assert gate.report(["some finding"], str_base="base-sha", int_changed_count=1) == 0


def test_the_report_fails_a_flagged_diff_with_no_justification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No ``test-change-ok`` trailer anywhere means the weakening blocks the PR."""
    monkeypatch.setattr(gate, "_git", lambda _args: "fix: unrelated commit body\n")

    assert gate.report(["some finding"], str_base="base-sha", int_changed_count=1) == 1


def test_a_bare_marker_with_no_reason_does_not_justify(monkeypatch: pytest.MonkeyPatch) -> None:
    """The reason is REQUIRED, matching ``gate-change-ok:``'s convention."""
    monkeypatch.setattr(gate, "_git", lambda _args: "test-change-ok:\n")

    assert gate.report(["some finding"], str_base="base-sha", int_changed_count=1) == 1


def test_env_reason_returns_the_stripped_value(monkeypatch: pytest.MonkeyPatch) -> None:
    """``TEST_CHANGE_OK`` is the one hatch reachable at commit time (blueprintx#941)."""
    monkeypatch.setenv("TEST_CHANGE_OK", "  fixing the pinned truncation value  ")

    assert gate.env_reason() == "fixing the pinned truncation value"


def test_env_reason_rejects_whitespace_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """A blank reason must not satisfy the hatch."""
    monkeypatch.setenv("TEST_CHANGE_OK", "   ")

    assert gate.env_reason() == ""


@pytest.mark.parametrize("str_marker", ["CI", "GITHUB_ACTIONS"])
def test_env_reason_is_ignored_under_ci(
    monkeypatch: pytest.MonkeyPatch, *, str_marker: str
) -> None:
    """A workflow ``env:`` line cannot stand in for a justification a reviewer can read."""
    monkeypatch.setenv("TEST_CHANGE_OK", "set by a workflow")
    monkeypatch.setenv(str_marker, "true")

    assert gate.env_reason() == ""


@pytest.mark.parametrize("str_value", ["false", "0", "no", "FALSE", ""])
def test_a_falsy_ci_value_is_not_ci(monkeypatch: pytest.MonkeyPatch, *, str_value: str) -> None:
    """``CI=false`` in a developer shell must not disable the local hatch."""
    monkeypatch.setenv("CI", str_value)
    monkeypatch.setenv("TEST_CHANGE_OK", "local reason")

    assert gate.env_reason() == "local reason"


@pytest.mark.parametrize("str_value", ["false", "0", ""])
def test_a_falsy_github_actions_value_is_still_ci(
    monkeypatch: pytest.MonkeyPatch, *, str_value: str
) -> None:
    """Presence alone means CI: a runner never sets ``GITHUB_ACTIONS`` falsy."""
    monkeypatch.setenv("GITHUB_ACTIONS", str_value)
    monkeypatch.setenv("TEST_CHANGE_OK", "a reason")

    assert gate.env_reason() == ""


def test_the_env_reason_wins_over_a_trailer(monkeypatch: pytest.MonkeyPatch) -> None:
    """With both sources valid, the env string is the one returned."""
    monkeypatch.setenv("TEST_CHANGE_OK", "from env")
    monkeypatch.setattr(gate, "_git", lambda _args: "test-change-ok: from a trailer\n")

    assert gate.justification_reason("base-sha") == "from env"


def test_a_blank_env_var_falls_back_to_a_trailer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A blank env var falls through to a valid trailer rather than blocking it."""
    monkeypatch.setenv("TEST_CHANGE_OK", "   ")
    monkeypatch.setattr(gate, "_git", lambda _args: "test-change-ok: from a trailer\n")

    assert gate.report(["some finding"], str_base="base-sha", int_changed_count=1) == 0


def test_the_report_passes_a_flagged_diff_with_the_env_justification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """THE SHOULD-PASS WITNESS: no finished commit and no PR, yet the report clears."""
    monkeypatch.setenv("TEST_CHANGE_OK", "fixing the ROUND_DOWN bug this test pins")
    monkeypatch.setattr(gate, "_git", lambda _args: "")

    assert gate.report(["some finding"], str_base="base-sha", int_changed_count=1) == 0


@pytest.mark.parametrize(
    "str_needle",
    [
        "TEST_CHANGE_OK='<reason>' git commit",
        "CI ignores the variable, so also add a 'test-change-ok: <reason>' line",
    ],
)
def test_the_unjustified_failure_says_how_to_justify_locally(
    monkeypatch: pytest.MonkeyPatch, *, capsys: pytest.CaptureFixture[str], str_needle: str
) -> None:
    """The error names the env var for a local commit and says the trailer is CI-only.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Replaces the git runner so no trailer is found.
    capsys : pytest.CaptureFixture[str]
        Captures the report text.
    str_needle : str
        The exact phrase the error must carry.
    """
    monkeypatch.setattr(gate, "_git", lambda _args: "")
    gate.report(["some finding"], str_base="base-sha", int_changed_count=1)

    assert str_needle in capsys.readouterr().out


@pytest.mark.parametrize(
    ("str_text", "bool_present"),
    [("TEST_CHANGE_OK is ignored under CI", True), ("git commit", False)],
    ids=["names-the-ignored-env-var", "omits-the-commit-advice"],
)
def test_the_ci_failure_leads_with_the_pr_body_line_not_the_env_var(
    monkeypatch: pytest.MonkeyPatch,
    *,
    capsys: pytest.CaptureFixture[str],
    str_text: str,
    bool_present: bool,
) -> None:
    """Under CI the advice names the PR-body line and says the env var is ignored.

    Parameters
    ----------
    monkeypatch : pytest.MonkeyPatch
        Sets the CI marker and removes any trailer.
    capsys : pytest.CaptureFixture[str]
        Captures the report text.
    str_text : str
        A fragment of the report.
    bool_present : bool
        Whether the fragment must appear in the report.
    """
    monkeypatch.setattr(gate, "_git", lambda _args: "")
    monkeypatch.setenv("CI", "true")
    gate.report(["some finding"], str_base="base-sha", int_changed_count=1)

    str_out = capsys.readouterr().out

    assert (str_text in str_out) is bool_present


def test_ci_ignores_test_change_ok_end_to_end(monkeypatch: pytest.MonkeyPatch) -> None:
    """Under CI the env hatch cannot justify a finding: ``report`` still fails."""
    monkeypatch.setattr(gate, "_git", lambda _args: "")
    monkeypatch.setenv("CI", "true")
    monkeypatch.setenv("TEST_CHANGE_OK", "a reason")

    assert gate.report(["some finding"], str_base="base-sha", int_changed_count=1) == 1


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
    assert "TestOne.test_v" in _sole_finding(str_old, str_new=str_new)


def test_a_unittest_call_rewritten_as_a_weaker_bare_assert_is_reported() -> None:
    """Changing the assertion's KIND must not hide the weakening.

    ``self.assertEqual(a, b)`` rewritten as ``assert a in b`` keeps the check count identical,
    so a same-kind comparison never sees it. The call is normalised to the operator it is
    equivalent to before the pair is compared.
    """
    assert "bare assert with in" in _sole_finding(
        'class T:\n\tdef test_v(self) -> None:\n\t\tself.assertEqual(a(), "send")\n',
        str_new='class T:\n\tdef test_v(self) -> None:\n\t\tassert a() in {"send", "recon"}\n',
    )


def test_a_unittest_call_rewritten_as_an_equivalent_bare_assert_is_clean() -> None:
    """⚠️ The other direction: the cross-kind rule must not fire on an ordinary refactor.

    Dropping ``unittest`` for a bare ``assert`` with the SAME operator asserts exactly as much.
    Without this case the rule above would also be satisfied by one that flags every rewrite,
    which is how a gate earns its way into everyone's escape hatch.
    """
    str_old = 'class T:\n\tdef test_v(self) -> None:\n\t\tself.assertEqual(a(), "send")\n'
    str_new = 'class T:\n\tdef test_v(self) -> None:\n\t\tassert a() == "send"\n'
    assert _findings(str_old, str_new=str_new) == []


def test_a_unittest_call_rewritten_as_a_stricter_bare_assert_is_clean() -> None:
    """A stricter operator after the rewrite is a strengthening, not a weakening."""
    str_old = "class T:\n\tdef test_v(self) -> None:\n\t\tself.assertIn(a(), [5])\n"
    str_new = "class T:\n\tdef test_v(self) -> None:\n\t\tassert a() == 5\n"
    assert _findings(str_old, str_new=str_new) == []


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
    assert "truthy constant" in _sole_finding(
        "class T:\n\tdef test_v(self) -> None:\n\t\tself.assertEqual(a(), 5)\n",
        str_new=f"class T:\n\tdef test_v(self) -> None:\n\t\t{str_new_assert}\n",
    )


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
    assert _findings(str_old, str_new=str_new) == []


def _git_in(path_repo: Path, *args: str) -> str:
    """Run ``git`` inside a throwaway repo and return its stripped stdout.

    Parameters
    ----------
    path_repo : pathlib.Path
        The repository to run in.
    *args : str
        Arguments after ``git``.

    Returns
    -------
    str
        Captured stdout, stripped.
    """
    cls_proc = subprocess.run(  # noqa: S603
        ["git", "-C", str(path_repo), *args],  # noqa: S607
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    return cls_proc.stdout.strip()


@pytest.fixture
def path_mid_merge(tmp_path: Path, *, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Return a repo whose ``feature`` has a merge of ``main`` in progress.

    ``main`` moves on after the fork, so a base resolved from the pre-merge HEAD (the fork
    point) differs from main's tip.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Pytest-provided scratch directory.
    monkeypatch : pytest.MonkeyPatch
        Used to run the gate inside the repo.

    Returns
    -------
    pathlib.Path
        The repository, left mid-merge.
    """
    _git_in(tmp_path, "init", "-q", "--initial-branch=main")
    _git_in(tmp_path, "config", "user.email", "t@example.com")
    _git_in(tmp_path, "config", "user.name", "t")
    _git_in(tmp_path, "config", "commit.gpgsign", "false")
    _git_in(tmp_path, "commit", "-q", "--allow-empty", "-m", "seed")
    _git_in(tmp_path, "checkout", "-q", "-b", "feature")
    (tmp_path / "own").write_text("own", encoding="utf-8")
    _git_in(tmp_path, "add", "own")
    _git_in(tmp_path, "commit", "-q", "-m", "own")
    _git_in(tmp_path, "checkout", "-q", "main")
    (tmp_path / "theirs").write_text("theirs", encoding="utf-8")
    _git_in(tmp_path, "add", "theirs")
    _git_in(tmp_path, "commit", "-q", "-m", "theirs")
    _git_in(tmp_path, "checkout", "-q", "feature")
    _git_in(tmp_path, "merge", "-q", "--no-commit", "--no-ff", "main")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(gate, "PATH_ROOT", tmp_path)
    return tmp_path


def test_resolve_base_mid_merge_is_the_incoming_tip(path_mid_merge: Path) -> None:
    """Mid-merge the base is main's tip, never the fork point that charges main's delta."""
    assert gate.resolve_base() == _git_in(path_mid_merge, "rev-parse", "main")


_STR_PAD = "".join(
    f"def test_p{int_i}() -> None:\n    assert g({int_i}) == {int_i}\n" for int_i in range(8)
)
_STR_STRONG = _STR_PAD + "def test_v() -> None:\n    assert f() == 1\n"
_STR_WEAK = _STR_PAD + "def test_v() -> None:\n    assert f() in (1, 2)\n"


def _gate_after_merge(
    path_repo: Path, *, monkeypatch: pytest.MonkeyPatch, str_main_body: str, str_feat_body: str
) -> int:
    """Run the gate mid-merge, after ``main`` and ``feature`` each moved on from the fork.

    Parameters
    ----------
    path_repo : pathlib.Path
        An empty directory to turn into the repository.
    monkeypatch : pytest.MonkeyPatch
        Used to run the gate inside the repo.
    str_main_body : str
        The test file's content as committed on ``main`` after the fork.
    str_feat_body : str
        The test file's content as committed on ``feature`` after the fork.

    Returns
    -------
    int
        The gate's exit code.
    """
    path_test = path_repo / "tests" / "test_a.py"
    path_test.parent.mkdir()
    _git_in(path_repo, "init", "-q", "--initial-branch=main")
    _git_in(path_repo, "config", "user.email", "t@example.com")
    _git_in(path_repo, "config", "user.name", "t")
    _git_in(path_repo, "config", "commit.gpgsign", "false")
    path_test.write_text(_STR_STRONG, encoding="utf-8")
    _git_in(path_repo, "add", ".")
    _git_in(path_repo, "commit", "-q", "-m", "seed")
    _git_in(path_repo, "checkout", "-q", "-b", "feature")
    (path_repo / "own").write_text("own", encoding="utf-8")
    path_test.write_text(str_feat_body, encoding="utf-8")
    _git_in(path_repo, "add", ".")
    _git_in(path_repo, "commit", "-q", "-m", "own")
    _git_in(path_repo, "checkout", "-q", "main")
    (path_repo / "theirs").write_text("theirs", encoding="utf-8")
    path_test.write_text(str_main_body, encoding="utf-8")
    _git_in(path_repo, "add", ".")
    _git_in(path_repo, "commit", "-q", "-m", "theirs")
    _git_in(path_repo, "checkout", "-q", "feature")
    _git_in(path_repo, "merge", "-q", "--no-commit", "--no-ff", "main")
    monkeypatch.chdir(path_repo)
    monkeypatch.setattr(gate, "PATH_ROOT", path_repo)
    return gate.main([])


def test_a_weakening_merged_in_from_main_is_not_charged_to_the_branch(
    tmp_path: Path, *, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Should-fail witness for #1060: main's own weakening must not block the branch."""
    assert (
        _gate_after_merge(
            tmp_path, monkeypatch=monkeypatch, str_main_body=_STR_WEAK, str_feat_body=_STR_STRONG
        )
        == 0
    )


def test_a_weakening_authored_on_the_branch_still_fails_after_the_merge(
    tmp_path: Path, *, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The other direction: narrowing the base must not blind the gate to the branch's own work."""
    assert (
        _gate_after_merge(
            tmp_path, monkeypatch=monkeypatch, str_main_body=_STR_STRONG, str_feat_body=_STR_WEAK
        )
        == 1
    )


@pytest.fixture
def path_renamed_repo(tmp_path: Path, *, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Return a repo on ``feature`` holding ``tests/test_old.py`` committed on ``main``.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Pytest-provided scratch directory.
    monkeypatch : pytest.MonkeyPatch
        Used to run the gate inside the repo.

    Returns
    -------
    pathlib.Path
            The repository, with the base commit on ``main``.
    """
    _git_in(tmp_path, "init", "-q", "--initial-branch=main")
    _git_in(tmp_path, "config", "user.email", "t@example.com")
    _git_in(tmp_path, "config", "user.name", "t")
    _git_in(tmp_path, "config", "commit.gpgsign", "false")
    _git_in(tmp_path, "config", "diff.renames", "false")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_old.py").write_text(_STR_STRONG, encoding="utf-8")
    _git_in(tmp_path, "add", "-A")
    _git_in(tmp_path, "commit", "-q", "-m", "seed")
    _git_in(tmp_path, "checkout", "-q", "-b", "feature")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(gate, "PATH_ROOT", tmp_path)
    return tmp_path


def _rename_with(path_repo: Path, *, str_body: str) -> list[str]:
    """Rename ``test_old.py`` to ``test_new.py`` with ``str_body``, stage, and run the gate.

    Parameters
    ----------
    path_repo : pathlib.Path
        The repository from ``path_renamed_repo``.
    str_body : str
        Content of the renamed file.

    Returns
    -------
    list of str
            The gate's findings.
    """
    _git_in(path_repo, "mv", "tests/test_old.py", "tests/test_new.py")
    (path_repo / "tests" / "test_new.py").write_text(str_body, encoding="utf-8")
    _git_in(path_repo, "add", "-A")
    str_base = _git_in(path_repo, "rev-parse", "main")
    return gate.collect_problems(gate.changed_paths(str_base), str_base=str_base)


def test_a_renamed_and_weakened_test_file_is_reported(path_renamed_repo: Path) -> None:
    """Renaming a test and weakening its assertion in one commit must fail the gate."""
    assert any(
        "test_new.py" in str_f for str_f in _rename_with(path_renamed_repo, str_body=_STR_WEAK)
    )


def test_a_merely_renamed_test_file_is_clean(path_renamed_repo: Path) -> None:
    """A pure rename keeps every assertion, so the gate stays green."""
    assert _rename_with(path_renamed_repo, str_body=_STR_STRONG) == []


def test_a_source_file_renamed_into_tests_touches_production_code() -> None:
    """A rename's SOURCE is removed, so moving ``src/`` into ``tests/`` changes production."""
    assert gate._touches_production_code([("R", "src/app.py", "tests/test_app.py")])


def test_a_test_file_moved_out_of_tests_is_reported(path_renamed_repo: Path) -> None:
    """Moving ``tests/test_old.py`` to ``src/`` removes its tests, so the gate names it."""
    (path_renamed_repo / "src").mkdir()
    _git_in(path_renamed_repo, "mv", "tests/test_old.py", "src/old.py")
    str_base = _git_in(path_renamed_repo, "rev-parse", "main")
    list_found = gate.collect_problems(gate.changed_paths(str_base), str_base=str_base)
    assert any("tests/test_old.py" in str_f for str_f in list_found)


def test_a_source_file_renamed_into_tests_is_not_read_as_an_old_test(
    path_renamed_repo: Path,
) -> None:
    """A ``src/`` file moved into ``tests/`` has no test baseline, so it is not compared."""
    (path_renamed_repo / "src").mkdir()
    (path_renamed_repo / "src" / "app.py").write_text(_STR_STRONG, encoding="utf-8")
    _git_in(path_renamed_repo, "add", "-A")
    _git_in(path_renamed_repo, "commit", "-q", "-m", "src")
    str_base = _git_in(path_renamed_repo, "rev-parse", "HEAD")
    _git_in(path_renamed_repo, "mv", "src/app.py", "tests/test_app.py")
    (path_renamed_repo / "tests" / "test_app.py").write_text(_STR_WEAK, encoding="utf-8")
    _git_in(path_renamed_repo, "add", "-A")
    assert gate.collect_problems(gate.changed_paths(str_base), str_base=str_base) == []


@pytest.mark.parametrize(
    ("str_status", "str_src", "str_dst", "bool_expected"),
    [
        ("D", "tests/test_a.py", "tests/test_a.py", True),
        ("D", "src/a.py", "src/a.py", False),
        ("R", "tests/test_a.py", "src/a.py", True),
        ("R", "tests/test_a.py", "tests/test_b.py", False),
        ("R", "src/a.py", "tests/test_a.py", False),
        ("R", "tests/test_a.py", "src/test_a.py", True),
    ],
)
def test_test_file_removed_classifies_each_row_shape(
    str_status: str, *, str_src: str, str_dst: str, bool_expected: bool
) -> None:
    """Only a deleted test, or one moved to a non-test path, has left the suite."""
    assert gate._test_file_removed(str_status, str_src=str_src, str_path=str_dst) is bool_expected


def test_moving_a_test_into_src_arms_the_expected_value_rule() -> None:
    """Intended: a test moved into ``src/`` is a production-path change for the whole diff."""
    assert gate._touches_production_code([("R", "tests/test_a.py", "src/a.py")])


def test_the_failure_says_interactive_terminal_only_when_no_terminal(
    monkeypatch: pytest.MonkeyPatch, *, capsys: pytest.CaptureFixture[str]
) -> None:
    """Without a readable ``/dev/tty`` the failure says a person must run the commit."""
    monkeypatch.setattr(gate, "_git", lambda _args: "")
    monkeypatch.setattr(sys.modules["gate_env"], "has_terminal", lambda: False)
    gate.report(["some finding"], str_base="base-sha", int_changed_count=1)

    assert "honored only in an interactive terminal" in capsys.readouterr().out


def test_the_failure_omits_the_terminal_hint_with_a_terminal(
    monkeypatch: pytest.MonkeyPatch, *, capsys: pytest.CaptureFixture[str]
) -> None:
    """With a terminal the failure keeps its current text."""
    monkeypatch.setattr(gate, "_git", lambda _args: "")
    monkeypatch.setattr(sys.modules["gate_env"], "has_terminal", lambda: True)
    gate.report(["some finding"], str_base="base-sha", int_changed_count=1)

    assert "interactive terminal" not in capsys.readouterr().out


def test_show_reads_blobs_from_the_root_not_the_process_cwd(
    tmp_path: Path, *, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Item 1 of #1258: ``show`` must run git in ``PATH_ROOT`` like ``_git`` does."""
    path_repo = tmp_path / "repo"
    path_repo.mkdir()
    _git_in(path_repo, "init", "-q")
    (path_repo / "a.py").write_text("X = 1\n", encoding="utf-8")
    _git_in(path_repo, "add", ".")
    path_elsewhere = tmp_path / "elsewhere"
    path_elsewhere.mkdir()
    monkeypatch.chdir(path_elsewhere)
    monkeypatch.setattr(gate, "PATH_ROOT", path_repo)
    assert gate.show(gate.STR_INDEX_REF, str_path="a.py") == "X = 1\n"


@pytest.mark.parametrize(
    "str_marker",
    ["@pytest.mark.skipif(True, reason='x')\n", "@pytest.mark.skipif(sys.platform == 'x')\n"],
)
def test_a_newly_added_skipif_marker_is_flagged(str_marker: str) -> None:
    """Item 5 of #1258: ``skipif`` escaped the ``skip``/``xfail`` match."""
    str_old = "def test_a():\n    assert f() == 1\n"
    str_new = f"{str_marker}def test_a():\n    assert f() == 1\n"
    assert "skipif" in _sole_finding(str_old, str_new=str_new)


def test_a_newly_added_pytest_skip_call_is_flagged() -> None:
    """Item 5 of #1258: ``pytest.skip()`` inside the body turns the test off too."""
    str_old = "def test_a():\n    assert f() == 1\n"
    str_new = "def test_a():\n    pytest.skip('later')\n    assert f() == 1\n"
    assert "skip()" in _sole_finding(str_old, str_new=str_new)


def test_raises_keyword_form_is_not_read_as_broadened() -> None:
    """Item 6 of #1258: ``expected_exception=ValueError`` is the same type as positional."""
    str_old = "def test_a():\n    with pytest.raises(ValueError):\n        f()\n"
    str_new = str_old.replace("(ValueError)", "(expected_exception=ValueError)")
    assert _findings(str_old, str_new=str_new) == []


def test_raises_keyword_form_broadened_to_exception_is_flagged() -> None:
    """Item 6 of #1258: reading the keyword must not blind the broadening check."""
    str_old = (
        "def test_a():\n    with pytest.raises(expected_exception=ValueError):\n        f()\n"
    )
    str_new = str_old.replace("ValueError", "Exception")
    assert "broadened" in _sole_finding(str_old, str_new=str_new)


@pytest.mark.parametrize("str_path", ["tests/conftest.py", "tests/helpers/util.py"])
def test_test_support_modules_are_not_production_code(str_path: str) -> None:
    """Item 7 of #1258: a fixture or helper under ``tests/`` is not production code."""
    assert not gate._touches_production_code([("M", str_path, str_path)])


def test_narrowing_skip_to_skipif_is_not_flagged() -> None:
    """An unconditional skip made conditional narrows the skip; it is not newly skipped."""
    str_old = "@pytest.mark.skip\ndef test_a():\n    assert f() == 1\n"
    str_new = "@pytest.mark.skipif(sys.platform == 'x')\ndef test_a():\n    assert f() == 1\n"
    assert _findings(str_old, str_new=str_new) == []


def test_adding_strict_to_an_xfail_is_not_flagged() -> None:
    """``xfail`` -> ``xfail(strict=True)`` tightens the marker; it is not newly marked."""
    str_old = "@pytest.mark.xfail\ndef test_a():\n    assert f() == 1\n"
    str_new = "@pytest.mark.xfail(strict=True)\ndef test_a():\n    assert f() == 1\n"
    assert _findings(str_old, str_new=str_new) == []


def test_nested_guards_equal_the_same_flat_skipif_condition() -> None:
    """``if a and b: if c: skip()`` -> ``@skipif(a and b and c)`` is the same condition moved."""
    str_old = (
        "def test_a():\n    if a and b:\n        if c:\n            pytest.skip()\n"
        "    assert f()\n"
    )
    str_new = "@pytest.mark.skipif(a and b and c)\ndef test_a():\n    assert f()\n"
    assert _findings(str_old, str_new=str_new) == []


def test_show_raises_when_git_cannot_be_spawned(monkeypatch: pytest.MonkeyPatch) -> None:
    """A gate that cannot run ``git`` stops; it does not report a comparison it never made."""
    monkeypatch.setattr(gate.subprocess, "run", MagicMock(side_effect=FileNotFoundError))
    with pytest.raises(FileNotFoundError):
        gate.show("HEAD", str_path="a.py")


def test_an_else_branch_skip_equals_the_negated_skipif_condition() -> None:
    """``if c: ... else: pytest.skip()`` -> ``@skipif(not c)`` is the same condition moved."""
    str_old = (
        "def test_a():\n    if c:\n        pass\n    else:\n        pytest.skip()\n"
        "    assert f()\n"
    )
    str_new = "@pytest.mark.skipif(not c)\ndef test_a():\n    assert f()\n"
    assert _findings(str_old, str_new=str_new) == []


def test_a_try_else_skip_is_conditional_not_unconditional() -> None:
    """A skip in ``try: ... else:`` runs only when the body raised nothing, so it is guarded."""
    str_old = (
        "def test_a():\n    try:\n        import db\n    except ImportError:\n        pass\n"
        "    else:\n        pytest.skip()\n    assert f()\n"
    )
    str_new = "@pytest.mark.skipif(True)\n" + str_old
    assert _sole_finding(str_old, str_new=str_new).endswith("newly marked skipif:True")


def test_widening_a_conditional_in_body_skip_to_skipif_is_flagged() -> None:
    """The in-body ``pytest.skip()`` is not the unconditional ``@skip`` decorator."""
    str_old = "def test_a():\n    if not DB:\n        pytest.skip()\n    assert f() == 1\n"
    str_new = "@pytest.mark.skipif(True)\ndef test_a():\n    assert f() == 1\n"
    assert "skipif" in _sole_finding(str_old, str_new=str_new)


def test_moving_an_unconditional_skip_into_a_conditional_body_skip_is_not_flagged() -> None:
    """``@skip`` -> ``if cond: pytest.skip()`` narrows the skip, like ``skip`` -> ``skipif``."""
    str_old = "@pytest.mark.skip\ndef test_a():\n    assert f() == 1\n"
    str_new = "def test_a():\n    if not DB:\n        pytest.skip()\n    assert f() == 1\n"
    assert _findings(str_old, str_new=str_new) == []


def test_a_changed_skipif_condition_is_flagged() -> None:
    """``skipif(a)`` -> ``skipif(True)`` widens the skip; the condition is part of the label."""
    str_old = "@pytest.mark.skipif(a)\ndef test_a():\n    assert f() == 1\n"
    str_new = "@pytest.mark.skipif(True)\ndef test_a():\n    assert f() == 1\n"
    assert "skipif:True" in _sole_finding(str_old, str_new=str_new)


def test_making_a_guarded_skip_unconditional_is_flagged() -> None:
    """``if not DB: pytest.skip()`` -> bare ``pytest.skip()`` turns the test off outright."""
    str_old = "def test_a():\n    if not DB:\n        pytest.skip()\n    assert f() == 1\n"
    str_new = "def test_a():\n    pytest.skip()\n    assert f() == 1\n"
    assert "skip()" in _sole_finding(str_old, str_new=str_new)


def test_skipif_to_a_guarded_body_skip_is_not_flagged() -> None:
    """``@skipif(c)`` -> ``if c: pytest.skip()`` is the same condition moved into the body."""
    str_old = "@pytest.mark.skipif(c)\ndef test_a():\n    assert f() == 1\n"
    str_new = "def test_a():\n    if c:\n        pytest.skip()\n    assert f() == 1\n"
    assert _findings(str_old, str_new=str_new) == []


_GUARDED = "def test_a():\n    if {cond}:\n        pytest.skip()\n    assert f() == 1\n"


def test_widening_a_guarded_skip_condition_is_flagged() -> None:
    """``if not DB: pytest.skip()`` -> ``if True: pytest.skip()`` skips everywhere."""
    found = _sole_finding(_GUARDED.format(cond="not DB"), str_new=_GUARDED.format(cond="True"))
    assert "skip(if):True" in found


def test_a_second_guarded_skip_is_flagged() -> None:
    """A new guarded skip with a new condition is a new way to turn the test off."""
    str_new = (
        "def test_a():\n    if not DB:\n        pytest.skip()\n"
        "    if True:\n        pytest.skip()\n    assert f() == 1\n"
    )
    assert "skip(if):True" in _sole_finding(_GUARDED.format(cond="not DB"), str_new=str_new)


def test_a_skip_wrapped_in_with_is_unconditional() -> None:
    """``with ctx: pytest.skip()`` always runs; it is not a guard."""
    str_new = "def test_a():\n    with ctx:\n        pytest.skip()\n    assert f() == 1\n"
    assert "skip()" in _sole_finding(_GUARDED.format(cond="not DB"), str_new=str_new)


def test_a_skip_in_a_nested_helper_is_not_a_skip() -> None:
    """A ``pytest.skip()`` inside a closure that is never called does not turn the test off."""
    str_new = "def test_a():\n    def helper():\n        pytest.skip()\n    assert f() == 1\n"
    assert _findings("def test_a():\n    assert f() == 1\n", str_new=str_new) == []


def test_skipif_to_a_body_skip_on_another_condition_is_flagged() -> None:
    """Moving ``@skipif(a)`` into ``if b: pytest.skip()`` changes the condition."""
    str_old = "@pytest.mark.skipif(a)\ndef test_a():\n    assert f() == 1\n"
    assert "skip(if):b" in _sole_finding(str_old, str_new=_GUARDED.format(cond="b"))


def test_a_guarded_body_skip_to_skipif_on_the_same_condition_is_not_flagged() -> None:
    """``if c: pytest.skip()`` -> ``@skipif(c)`` is the same condition moved out."""
    str_new = "@pytest.mark.skipif(c)\ndef test_a():\n    assert f() == 1\n"
    assert _findings(_GUARDED.format(cond="c"), str_new=str_new) == []


def test_an_unconditional_skip_in_the_other_spelling_is_not_flagged() -> None:
    """``@skip`` -> bare ``pytest.skip()`` is the same unconditional skip."""
    str_old = "@pytest.mark.skip\ndef test_a():\n    assert f() == 1\n"
    str_new = "def test_a():\n    pytest.skip()\n    assert f() == 1\n"
    assert _findings(str_old, str_new=str_new) == []


_EXCEPT_SKIP = (
    "def test_a():\n    try:\n        import db\n    except ImportError:\n"
    "        pytest.skip()\n    assert f() == 1\n"
)


def test_adding_skip_to_an_except_guarded_skip_is_flagged() -> None:
    """A skip that only ran when an import failed is conditional, so ``@skip`` is new."""
    str_new = "@pytest.mark.skip\n" + _EXCEPT_SKIP
    assert _sole_finding(_EXCEPT_SKIP, str_new=str_new).endswith("newly marked skip")


def test_adding_an_except_guarded_skip_is_not_unconditional() -> None:
    """The idiomatic ``except ImportError: pytest.skip()`` is a guarded skip."""
    found = _sole_finding("def test_a():\n    assert f() == 1\n", str_new=_EXCEPT_SKIP)
    assert "skip(if):except" in found


def test_nested_guards_are_all_kept() -> None:
    """``if a: if b: skip`` moved to ``@skipif(b)`` widens the skip; ``a`` is part of the guard."""
    str_old = "def test_a():\n    if a:\n        if b:\n            pytest.skip()\n    assert 1\n"
    str_new = "@pytest.mark.skipif(b)\ndef test_a():\n    assert 1\n"
    assert "skipif:b" in _sole_finding(str_old, str_new=str_new)


_EXC = (
    "def test_a():\n    try:\n        {body}\n    except {exc}:\n"
    "        pytest.skip()\n    assert 1\n"
)


def test_changing_the_except_type_of_a_skip_is_flagged() -> None:
    """Skipping on ``AssertionError`` turns a failing test into a green one."""
    str_old = _EXC.format(body="import db", exc="ImportError")
    str_new = _EXC.format(body="import db", exc="AssertionError")
    assert "except AssertionError" in _sole_finding(str_old, str_new=str_new)


def test_widening_the_except_type_of_a_skip_is_flagged() -> None:
    """``except ImportError`` -> ``except Exception`` skips on far more."""
    str_old = _EXC.format(body="import db", exc="ImportError")
    str_new = _EXC.format(body="import db", exc="Exception")
    assert "except Exception" in _sole_finding(str_old, str_new=str_new)


def test_an_always_true_loop_skip_is_unconditional() -> None:
    """``while True: pytest.skip()`` always runs; it is not a guard."""
    str_old = "def test_a():\n    while c:\n        pytest.skip()\n    assert 1\n"
    str_new = "def test_a():\n    while True:\n        pytest.skip()\n    assert 1\n"
    assert "skip()" in _sole_finding(str_old, str_new=str_new)


@pytest.mark.parametrize(
    ("str_call", "str_label"),
    [
        ("pytest.importorskip('db')", "importorskip()"),
        ("pytest.xfail('no')", "xfail()"),
        ("skip()", "skip()"),
    ],
)
def test_other_ways_to_turn_a_test_off_are_flagged(*, str_call: str, str_label: str) -> None:
    """``importorskip``, ``xfail()`` and the ``from pytest import skip`` form are skips too."""
    str_new = f"def test_a():\n    {str_call}\n    assert f() == 1\n"
    assert str_label in _sole_finding("def test_a():\n    assert f() == 1\n", str_new=str_new)


def test_dropping_xfail_strict_is_flagged() -> None:
    """A lax ``xfail`` lets an XPASS through; ``strict=True`` -> lax is a weakening."""
    str_old = "@pytest.mark.xfail(strict=True)\ndef test_a():\n    assert f() == 1\n"
    str_new = "@pytest.mark.xfail\ndef test_a():\n    assert f() == 1\n"
    assert _sole_finding(str_old, str_new=str_new).endswith("newly marked xfail:;lax")


def test_skipif_with_two_conditions_matches_an_or_guard() -> None:
    """``skipif(a, b)`` skips when either holds, the same as ``if a or b: pytest.skip()``."""
    str_old = "@pytest.mark.skipif(a, b)\ndef test_a():\n    assert f() == 1\n"
    str_new = "def test_a():\n    if a or b:\n        pytest.skip()\n    assert f() == 1\n"
    assert _findings(str_old, str_new=str_new) == []


def test_nested_or_guard_is_parenthesised() -> None:
    """``if a or b: if c: skip`` is ``(a or b) and (c)``, not ``a or b and c``."""
    str_old = (
        "def test_a():\n    if a or b:\n        if c:\n            pytest.skip()\n    assert 1\n"
    )
    str_new = "@pytest.mark.skipif(a or b and c)\ndef test_a():\n    assert 1\n"
    assert "skipif:a or (b and c)" in _sole_finding(str_old, str_new=str_new)


def test_while_one_is_unconditional() -> None:
    """``while 1: pytest.skip()`` always runs, like ``while True``."""
    str_old = "def test_a():\n    while c:\n        pytest.skip()\n    assert 1\n"
    str_new = "def test_a():\n    while 1:\n        pytest.skip()\n    assert 1\n"
    assert "skip()" in _sole_finding(str_old, str_new=str_new)


def test_xfail_call_after_an_unconditional_skip_is_not_flagged() -> None:
    """A test already skipped outright gains nothing from an added ``pytest.xfail()``."""
    str_old = "@pytest.mark.skip\ndef test_a():\n    assert 1\n"
    str_new = "@pytest.mark.skip\ndef test_a():\n    pytest.xfail()\n    assert 1\n"
    assert _findings(str_old, str_new=str_new) == []


_SKIPIF_COND = "@pytest.mark.skipif(cond)\ndef test_a():\n    assert 1\n"
_BODY = "    assert 1\n"


@pytest.mark.parametrize(
    ("str_old", "str_new"),
    [
        (
            "@pytest.mark.skipif(c)\ndef test_a():\n" + _BODY,
            "def test_a():\n    if not not c:\n        pytest.skip()\n" + _BODY,
        ),
        (
            "@pytest.mark.skipif(a and b)\ndef test_a():\n" + _BODY,
            "def test_a():\n    if b and a:\n        pytest.skip()\n" + _BODY,
        ),
        (
            "@pytest.mark.skipif(\"sys.platform == 'win32'\")\ndef test_a():\n" + _BODY,
            "def test_a():\n    if sys.platform == 'win32':\n        pytest.skip()\n" + _BODY,
        ),
        (
            _SKIPIF_COND,
            "def test_a():\n    cond and pytest.skip()\n" + _BODY,
        ),
        (
            "@pytest.mark.skipif(not cond)\ndef test_a():\n" + _BODY,
            "def test_a():\n    cond or pytest.skip()\n" + _BODY,
        ),
    ],
    ids=["double-not", "and-order", "string-condition", "and-short-circuit", "or-short-circuit"],
)
def test_a_moved_guard_spelled_differently_is_the_same_guard(
    *, str_old: str, str_new: str
) -> None:
    """Items of #1316: ``not not c``, operand order, a string condition and ``c and skip()``."""
    assert _findings(str_old, str_new=str_new) == []


def test_a_skip_call_in_an_if_test_is_unconditional() -> None:
    """Item of #1316: the test of an ``if`` always runs, so a skip there is unconditional."""
    str_new = "def test_a():\n    if pytest.skip():\n        pass\n" + _BODY
    assert "newly marked skip()" in _sole_finding("def test_a():\n" + _BODY, str_new=str_new)


def test_a_short_circuit_skip_keeps_its_guard() -> None:
    """Item of #1316: ``cond and pytest.skip()`` is conditional, not an outright skip."""
    str_new = "def test_a():\n    cond and pytest.skip()\n" + _BODY
    assert "skip(if):cond" in _sole_finding("def test_a():\n" + _BODY, str_new=str_new)


@pytest.mark.parametrize(
    ("str_skip", "str_label"),
    [
        ("    pt.skip()\n", "newly marked skip()"),
        ("    raise pt.skip.Exception('x')\n", "newly marked skip()"),
        ("    request.applymarker(pytest.mark.skip)\n", "newly marked applymarker-skip()"),
        (
            "    request.node.add_marker(pytest.mark.xfail)\n",
            "newly marked applymarker-xfail:;lax()",
        ),
    ],
    ids=["alias", "raise-exception", "applymarker", "add-marker"],
)
def test_an_unlisted_spelling_of_skip_is_detected(*, str_skip: str, str_label: str) -> None:
    """Item of #1316: ``import pytest as pt``, ``raise``, ``applymarker`` and ``add_marker``."""
    str_head = "import pytest\nimport pytest as pt\n\n\ndef test_a(request):\n"
    assert str_label in _sole_finding(str_head + _BODY, str_new=str_head + str_skip + _BODY)


def test_a_local_helper_named_skip_is_not_pytests() -> None:
    """Item of #1316: a ``def skip`` the module defines is not ``pytest.skip``."""
    str_old = "def skip():\n    pass\n\n\ndef test_a():\n" + _BODY
    str_new = "def skip():\n    pass\n\n\ndef test_a():\n    skip()\n" + _BODY
    assert _findings(str_old, str_new=str_new) == []


def test_a_module_pytestmark_is_a_new_marker() -> None:
    """Item of #1316: ``pytestmark = pytest.mark.skip`` newly skips every test below it."""
    str_new = "pytestmark = pytest.mark.skip\n\n\ndef test_a():\n" + _BODY
    assert "newly marked skip" in _sole_finding("def test_a():\n" + _BODY, str_new=str_new)


@pytest.mark.parametrize(
    "str_assign",
    ["pytestmark: list = [pytest.mark.skip]", "pytestmark += [pytest.mark.skip]"],
    ids=["annotated", "augmented"],
)
def test_an_annotated_or_augmented_pytestmark_is_a_new_marker(str_assign: str) -> None:
    """Review of #1328: ``pytestmark`` set by ``AnnAssign`` or ``AugAssign`` is read too."""
    str_head = "import pytest\npytestmark = []\n\n\ndef test_a():\n"
    str_new = "import pytest\npytestmark = []\n" + str_assign + "\n\n\ndef test_a():\n"
    assert "newly marked skip" in _sole_finding(str_head + _BODY, str_new=str_new + _BODY)


def test_dropping_a_redundant_run_true_is_not_flagged() -> None:
    """Review of #1328: ``run=True`` is the default, so removing it changes nothing."""
    str_old = "@pytest.mark.xfail(strict=True, run=True)\ndef test_a():\n" + _BODY
    str_new = "@pytest.mark.xfail(strict=True)\ndef test_a():\n" + _BODY
    assert _findings(str_old, str_new=str_new) == []


def test_a_negated_guard_compares_equal_whatever_the_operand_order() -> None:
    """Review of #1328: ``not (a and b)`` equals ``not (b and a)``."""
    str_old = "def test_a():\n    if not (a and b):\n        pytest.skip()\n" + _BODY
    str_new = "def test_a():\n    if not (b and a):\n        pytest.skip()\n" + _BODY
    assert _findings(str_old, str_new=str_new) == []


def test_a_string_if_test_is_not_read_as_the_expression_it_spells() -> None:
    """Review of #1328: ``if "x"`` is always true, so it is not the guard ``if x``."""
    str_old = "def test_a():\n    if x:\n        pytest.skip()\n" + _BODY
    str_new = "def test_a():\n    if 'x':\n        pytest.skip()\n" + _BODY
    assert "newly marked" in _sole_finding(str_old, str_new=str_new)


def test_a_pytestmark_under_an_if_is_a_new_marker() -> None:
    """Review of #1328: ``if sys.platform == ...: pytestmark = ...`` still skips the module."""
    str_new = "if sys.platform == 'win32':\n    pytestmark = pytest.mark.skip\n\n\ndef test_a():\n"
    assert "newly marked skip" in _sole_finding("def test_a():\n" + _BODY, str_new=str_new + _BODY)


def test_an_outright_skip_is_flagged_beside_a_conditional_module_skip() -> None:
    """Review of #1328: a platform-only ``pytestmark`` does not excuse a new outright skip."""
    str_head = "if sys.platform == 'win32':\n    pytestmark = pytest.mark.skip\n\n\n"
    str_old = str_head + "def test_a():\n" + _BODY
    str_new = str_head + "@pytest.mark.skip\ndef test_a():\n" + _BODY
    assert "newly marked skip" in _sole_finding(str_old, str_new=str_new)


def test_an_xfail_that_starts_running_is_a_tightening() -> None:
    """Review of #1328: dropping ``run=False`` makes the test run again."""
    str_old = "@pytest.mark.xfail(strict=True, run=False)\ndef test_a():\n" + _BODY
    str_new = "@pytest.mark.xfail(strict=True)\ndef test_a():\n" + _BODY
    assert _findings(str_old, str_new=str_new) == []


def test_a_pytestmark_in_an_except_handler_is_a_new_marker() -> None:
    """Review of #1328: ``except ImportError: pytestmark = ...`` skips the module too."""
    str_new = "try:\n    import foo\nexcept ImportError:\n    pytestmark = pytest.mark.skip\n"
    str_new += "\n\ndef test_a():\n" + _BODY
    assert "newly marked skip" in _sole_finding("def test_a():\n" + _BODY, str_new=str_new)


def test_making_a_run_false_xfail_strict_is_a_tightening() -> None:
    """Review of #1328: ``strict=True`` on ``xfail(run=False)`` only tightens it."""
    str_old = "@pytest.mark.xfail(run=False)\ndef test_a():\n" + _BODY
    str_new = "@pytest.mark.xfail(strict=True, run=False)\ndef test_a():\n" + _BODY
    assert _findings(str_old, str_new=str_new) == []


def test_adding_raises_to_a_run_false_xfail_is_a_tightening() -> None:
    """Review of #1328: ``raises=`` on ``xfail(run=False)`` only tightens it."""
    str_old = "@pytest.mark.xfail(run=False)\ndef test_a():\n" + _BODY
    str_new = "@pytest.mark.xfail(raises=ValueError, run=False)\ndef test_a():\n" + _BODY
    assert _findings(str_old, str_new=str_new) == []


@pytest.mark.parametrize(
    "str_mark",
    ["pytest.mark.xfail", "pytest.mark.skipif(c)"],
    ids=["xfail", "skipif"],
)
def test_a_guarded_pytestmark_keeps_its_guard(str_mark: str) -> None:
    """Review of #1328: an outright ``xfail`` is flagged beside a guarded ``pytestmark``."""
    str_head = f"if sys.platform == 'win32':\n    pytestmark = {str_mark}\n\n\n"
    str_old = str_head + "def test_a():\n" + _BODY
    str_new = str_head + "@pytest.mark.xfail\ndef test_a():\n" + _BODY
    assert "newly marked xfail" in _sole_finding(str_old, str_new=str_new)


def test_nested_pytestmark_guards_are_composed() -> None:
    """Review of #1328: ``if a: if b:`` guards the marker by ``a and b``."""
    str_head = "if a:\n    if b:\n        pytestmark = pytest.mark.skip\n\n\n"
    str_moved = "if b:\n    if a:\n        pytestmark = pytest.mark.skip\n\n\n"
    str_old = str_head + "def test_a():\n" + _BODY
    assert _findings(str_old, str_new=str_moved + "def test_a():\n" + _BODY) == []


def test_a_second_import_guarded_skip_is_not_excused_by_the_first() -> None:
    """Review of #1328: two ``try`` blocks are two guards, not one literal ``try``."""
    str_one = "try:\n    import foo\nexcept ImportError:\n    pytestmark = pytest.mark.skip\n"
    str_two = "try:\n    import bar\nexcept ImportError:\n    pytestmark = pytest.mark.skip\n"
    str_old = str_one + "\n\ndef test_a():\n" + _BODY
    str_new = str_one + str_two + "\n\ndef test_a():\n" + _BODY
    assert "newly marked skip" in _sole_finding(str_old, str_new=str_new)


def test_a_walrus_guard_keeps_its_operand_order() -> None:
    """Review of #1328: ``a and (a := True)`` is not ``(a := True) and a``."""
    str_old = "def test_a():\n    if a and (a := True):\n        pytest.skip()\n" + _BODY
    str_new = "def test_a():\n    if (a := True) and a:\n        pytest.skip()\n" + _BODY
    assert "newly marked" in _sole_finding(str_old, str_new=str_new)


def test_a_plain_import_unbinds_a_pytest_alias() -> None:
    """Review of #1328: ``import unittest as pt`` after ``import pytest as pt`` rebinds it."""
    str_head = "import pytest as pt\nimport unittest as pt\n\n\n"
    str_old = str_head + "def test_a():\n    pt.skip()\n" + _BODY
    str_new = str_head + "@pytest.mark.skip\ndef test_a():\n" + _BODY
    assert "newly marked skip" in _sole_finding(str_old, str_new=str_new)


def test_a_pytestmark_in_a_finally_block_is_a_new_marker() -> None:
    """Review of #1328: ``finally: pytestmark = ...`` runs on import."""
    str_new = "try:\n    pass\nfinally:\n    pytestmark = pytest.mark.skip\n\n\ndef test_a():\n"
    assert "newly marked skip" in _sole_finding("def test_a():\n" + _BODY, str_new=str_new + _BODY)


def test_a_runtime_skip_does_not_excuse_a_new_xfail() -> None:
    """Review of #1328: an assertion that failed before ``pytest.skip()`` now xfails."""
    str_old = "def test_a():\n    pytest.skip()\n" + _BODY
    str_new = "@pytest.mark.xfail\ndef test_a():\n    pytest.skip()\n" + _BODY
    assert "newly marked xfail" in _sole_finding(str_old, str_new=str_new)


def test_a_late_skip_marker_does_not_excuse_a_new_skip_decorator() -> None:
    """Review of #1328: a mark added during the test is not evaluated, so the body still runs."""
    str_old = "def test_a(request):\n    request.applymarker(pytest.mark.skip)\n" + _BODY
    str_new = "@pytest.mark.skip\n" + str_old
    assert "newly marked skip" in _sole_finding(str_old, str_new=str_new)


def test_a_guarded_late_marker_does_not_excuse_a_skipif_decorator() -> None:
    """Review of #1328: ``if c: request.node.add_marker(...)`` never stops the body running."""
    str_old = (
        "def test_a(request):\n    if c:\n        request.node.add_marker(pytest.mark.skip)\n"
    )
    str_new = "@pytest.mark.skipif(c, reason='r')\n" + str_old
    assert "newly marked skipif:c" in _sole_finding(str_old + _BODY, str_new=str_new + _BODY)


def test_a_keyword_condition_replaces_the_positional_ones() -> None:
    """Review of #1328: pytest reads ``condition=`` and ignores the positional conditions."""
    str_old = "@pytest.mark.xfail(True, condition=False, strict=True)\ndef test_a():\n" + _BODY
    str_new = "@pytest.mark.xfail(False, condition=True, strict=True)\ndef test_a():\n" + _BODY
    assert "newly marked xfail" in _sole_finding(str_old, str_new=str_new)


def test_an_assignment_unbinds_an_imported_skip() -> None:
    """Review of #1328: ``skip = lambda ...`` after ``from pytest import skip`` is not pytest's."""
    str_head = "from pytest import skip\nskip = lambda reason: None\n\n\n"
    str_old = str_head + "def test_a():\n    skip('r')\n" + _BODY
    str_new = str_head + "@pytest.mark.skip\ndef test_a():\n    skip('r')\n" + _BODY
    assert "newly marked skip" in _sole_finding(str_old, str_new=str_new)


def test_a_late_xfail_keeps_its_settings() -> None:
    """Review of #1328: dropping ``raises=`` from a late xfail widens what it excuses."""
    str_head = "def test_a(request):\n    request.applymarker(pytest.mark.xfail("
    str_old = str_head + "raises=ValueError, strict=True))\n" + _BODY
    str_new = str_head + "strict=True))\n" + _BODY
    assert "newly marked applymarker-xfail" in _sole_finding(str_old, str_new=str_new)


def test_a_handler_is_guarded_by_the_handlers_before_it() -> None:
    """Review of #1328: removing the first handler lets the second one run and skip."""
    str_try = "try:\n    import foo\n"
    str_first = "except ValueError:\n    pass\n"
    str_second = "except Exception:\n    pytestmark = pytest.mark.skip\n"
    str_tail = "\n\ndef test_a():\n" + _BODY
    str_old = str_try + str_first + str_second + str_tail
    assert "newly marked skip" in _sole_finding(str_old, str_new=str_try + str_second + str_tail)


@pytest.mark.parametrize(
    "str_stmt",
    [
        "request.applymarker(pytest.mark.xfail({}))",
        "if c:\n        request.node.add_marker(pytest.mark.xfail({}))",
    ],
    ids=["plain", "guarded"],
)
class TestLateXfailTightening:
    """Review of #1328: a late xfail is compared with late xfails under the same guard."""

    _HEAD = "def test_a(request):\n    "

    def _findings(self, str_stmt: str, *, str_old_args: str, str_new_args: str) -> list:
        return _findings(
            self._HEAD + str_stmt.format(str_old_args) + "\n" + _BODY,
            str_new=self._HEAD + str_stmt.format(str_new_args) + "\n" + _BODY,
        )

    def test_strict_is_a_tightening(self, str_stmt: str) -> None:
        """Adding ``strict=True`` is a tightening."""
        assert self._findings(str_stmt, str_old_args="", str_new_args="strict=True") == []

    def test_adding_raises_is_a_tightening(self, str_stmt: str) -> None:
        """Adding ``raises=`` is a tightening."""
        str_new = "strict=True, raises=ValueError"
        assert self._findings(str_stmt, str_old_args="strict=True", str_new_args=str_new) == []

    def test_dropping_strict_is_flagged(self, str_stmt: str) -> None:
        """Dropping ``strict=True`` is flagged."""
        str_found = self._findings(str_stmt, str_old_args="strict=True", str_new_args="")
        assert "newly marked applymarker-xfail" in str_found[0]

    def test_dropping_raises_is_flagged(self, str_stmt: str) -> None:
        """Dropping ``raises=`` is flagged."""
        str_old = "strict=True, raises=ValueError"
        str_found = self._findings(str_stmt, str_old_args=str_old, str_new_args="strict=True")
        assert "newly marked applymarker-xfail" in str_found[0]


def test_a_class_marker_is_a_new_marker() -> None:
    """Item of #1316: a skip decorator on the class newly skips its methods."""
    str_old = "class TestA:\n    def test_a(self):\n    " + _BODY
    str_new = "@pytest.mark.skip\nclass TestA:\n    def test_a(self):\n    " + _BODY
    assert "TestA.test_a() newly marked skip" in _sole_finding(str_old, str_new=str_new)


def test_a_skip_moved_from_the_function_to_its_class_is_not_flagged() -> None:
    """The same outright skip, one level up, adds nothing."""
    str_old = "class TestA:\n    @pytest.mark.skip\n    def test_a(self):\n    " + _BODY
    str_new = "@pytest.mark.skip\nclass TestA:\n    def test_a(self):\n    " + _BODY
    assert _findings(str_old, str_new=str_new) == []


@pytest.mark.parametrize(
    ("str_old_mark", "str_new_mark"),
    [
        ("xfail(strict=True, raises=ValueError)", "xfail(strict=True)"),
        ("xfail(strict=True)", "xfail(strict=True, run=False)"),
    ],
    ids=["raises-dropped", "run-false"],
)
def test_an_xfail_that_loses_raises_or_stops_running_is_flagged(
    *, str_old_mark: str, str_new_mark: str
) -> None:
    """Item of #1316: ``raises=`` and ``run=`` are part of the ``xfail`` marker."""
    str_old = f"@pytest.mark.{str_old_mark}\ndef test_a():\n{_BODY}"
    str_new = f"@pytest.mark.{str_new_mark}\ndef test_a():\n{_BODY}"
    assert "newly marked xfail" in _sole_finding(str_old, str_new=str_new)


def test_an_xfail_that_gains_raises_is_a_tightening() -> None:
    """Narrowing an ``xfail`` to one exception type is not a new marker."""
    str_old = "@pytest.mark.xfail(strict=True)\ndef test_a():\n" + _BODY
    str_new = "@pytest.mark.xfail(strict=True, raises=ValueError)\ndef test_a():\n" + _BODY
    assert _findings(str_old, str_new=str_new) == []


def test_an_xfail_decorator_after_an_unconditional_skip_is_not_flagged() -> None:
    """Item of #1316: the decorator is exempt exactly as the ``pytest.xfail()`` call is."""
    str_old = "@pytest.mark.skip\ndef test_a():\n" + _BODY
    str_new = "@pytest.mark.xfail\ndef test_a():\n" + _BODY
    assert _findings(str_old, str_new=str_new) == []


@pytest.mark.parametrize(
    ("str_old_head", "str_new_head"),
    [
        ("match v:\n        case 1:\n", "match w:\n        case 1:\n"),
        ("match v:\n        case 1 if g1:\n", "match v:\n        case 1 if g2:\n"),
        (
            "try:\n        a()\n    except E:\n",
            "try:\n        b()\n    except E:\n",
        ),
    ],
    ids=["match-subject", "match-case-guard", "except-try-body"],
)
def test_a_guard_that_names_something_else_is_a_new_skip(
    *, str_old_head: str, str_new_head: str
) -> None:
    """Item of #1316: ``match`` labels carry subject and guard, ``except`` its ``try`` body."""
    str_tail = "            pytest.skip()\n" + _BODY
    str_old = "def test_a(v):\n    " + str_old_head + str_tail
    str_new = "def test_a(v):\n    " + str_new_head + str_tail
    assert "newly marked skip(if)" in _sole_finding(str_old, str_new=str_new)


def test_a_skipif_moved_into_applymarker_keeps_its_condition() -> None:
    """Review of #1328 (#1334): ``@skipif(c)`` moved into ``applymarker`` adds nothing."""
    str_old = "@pytest.mark.skipif(c)\ndef test_a(request):\n" + _BODY
    str_new = "def test_a(request):\n    request.applymarker(pytest.mark.skipif(c))\n" + _BODY
    assert _findings(str_old, str_new=str_new) == []


def test_applymarker_of_something_that_is_not_pytest_mark_is_not_a_skip() -> None:
    """Review of #1328 (#1334): the receiver must be ``pytest.mark``, not any ``.skip``."""
    str_old = "def test_a(request):\n" + _BODY
    str_new = "def test_a(request):\n    request.applymarker(other.skip)\n" + _BODY
    assert _findings(str_old, str_new=str_new) == []


def test_an_edited_numeric_try_argument_under_an_unchanged_except_skip_is_reported() -> None:
    """Owner decision on #1340: a number is a literal too, so editing it is a finding."""
    str_tail = "    except E:\n        pytest.skip()\n" + _BODY
    str_old = "def test_a():\n    try:\n        f(1)\n" + str_tail
    str_new = "def test_a():\n    try:\n        f(2)\n" + str_tail
    assert "newly marked" in _sole_finding(str_old, str_new=str_new)


def test_an_xfail_raises_tuple_reordered_is_not_a_new_marker() -> None:
    """Review of #1328 (#1334): ``raises=(A, B)`` and ``raises=(B, A)`` name the same types."""
    str_old = "@pytest.mark.xfail(raises=(A, B))\ndef test_a():\n" + _BODY
    str_new = "@pytest.mark.xfail(raises=(B, A))\ndef test_a():\n" + _BODY
    assert _findings(str_old, str_new=str_new) == []


@pytest.mark.parametrize(
    "str_head",
    [
        "try:\n    from helpers import skip\nexcept ImportError:\n    pass\n",
        "if TYPE_CHECKING:\n    from helpers import skip\n",
    ],
    ids=["try", "if"],
)
def test_a_skip_imported_from_elsewhere_inside_try_or_if_is_a_helper(str_head: str) -> None:
    """Review of #1328 (#1334): a module-level ``skip`` bound under ``try``/``if`` is no pytest."""
    str_old = "def test_a():\n" + _BODY
    str_new = str_head + "\n\ndef test_a():\n    skip()\n" + _BODY
    assert _findings(str_old, str_new=str_new) == []


def test_a_parameter_named_skip_is_not_pytest_skip() -> None:
    """Review of #1328 (#1334): a fixture or parameter named ``skip`` shadows the bare name."""
    str_old = "def test_a():\n" + _BODY
    str_new = "def test_a(skip):\n    skip()\n" + _BODY
    assert _findings(str_old, str_new=str_new) == []


def test_a_function_local_import_of_skip_is_not_pytest_skip() -> None:
    """Review of #1328 (#1334): ``from helpers import skip`` inside the test shadows pytest's."""
    str_old = "def test_a():\n" + _BODY
    str_new = "def test_a():\n    from helpers import skip\n\n    skip()\n" + _BODY
    assert _findings(str_old, str_new=str_new) == []


@pytest.mark.parametrize(
    "str_head",
    [
        "for x in y:\n    pytestmark = pytest.mark.skip\n",
        "with ctx:\n    pytestmark = pytest.mark.skip\n",
        "match v:\n    case _:\n        pytestmark = pytest.mark.skip\n",
        "try:\n    pass\nexcept* E:\n    pytestmark = pytest.mark.skip\n",
    ],
    ids=["for", "with", "match", "trystar"],
)
def test_a_pytestmark_under_for_with_match_or_trystar_is_a_new_marker(str_head: str) -> None:
    """Review of #1328 (#1334): ``pytestmark`` set inside these blocks still marks the module."""
    str_old = "def test_a():\n" + _BODY
    str_new = str_head + "\n\ndef test_a():\n" + _BODY
    assert "newly marked skip" in _sole_finding(str_old, str_new=str_new)


def test_a_skip_in_a_match_case_guard_is_a_new_skip() -> None:
    """Review of #1328 (#1334): the ``case ... if <guard>`` expression is read like an ``if``."""
    str_old = "def test_a(v):\n" + _BODY
    str_new = (
        "def test_a(v):\n    match v:\n        case 1 if pytest.skip():\n            pass\n"
        + _BODY
    )
    assert "newly marked skip" in _sole_finding(str_old, str_new=str_new)


def test_adding_a_callee_to_the_try_body_reports_the_except_skip_again() -> None:
    """Review of #1340: a new call in the ``try`` body is a different guard."""
    str_tail = "    except E:\n        pytest.skip()\n" + _BODY
    str_old = "def test_a():\n    try:\n        f(1)\n" + str_tail
    str_new = "def test_a():\n    try:\n        f(1)\n        g()\n" + str_tail
    assert "newly marked skip(if)" in _sole_finding(str_old, str_new=str_new)


def test_a_try_body_importing_something_else_is_a_new_except_skip() -> None:
    """Review of #1340: two call-free ``try`` bodies keep distinct keys through their imports."""
    str_tail = "    except ImportError:\n        pytest.skip()\n" + _BODY
    str_old = "def test_a():\n    try:\n        import foo\n" + str_tail
    str_new = "def test_a():\n    try:\n        import bar\n" + str_tail
    assert "newly marked skip(if)" in _sole_finding(str_old, str_new=str_new)


@pytest.mark.parametrize("str_call", ["mark.skip", "mark.skip()"])
def test_applymarker_through_from_pytest_import_mark_is_a_new_skip(str_call: str) -> None:
    """Review of #1340: ``from pytest import mark`` is still ``pytest.mark``."""
    str_head = "from pytest import mark\n\n\n"
    str_old = str_head + "def test_a(request):\n" + _BODY
    str_new = str_head + f"def test_a(request):\n    request.applymarker({str_call})\n" + _BODY
    assert "newly marked applymarker-skip" in _sole_finding(str_old, str_new=str_new)


def test_a_guarded_applymarker_skipif_is_not_the_unguarded_decorator() -> None:
    """Review of #1340: ``if flag: applymarker(skipif(c))`` skips on ``c and flag``, a new skip."""
    str_old = "@pytest.mark.skipif(c)\ndef test_a(request):\n" + _BODY
    str_new = (
        "def test_a(request, flag):\n    if flag:\n"
        "        request.applymarker(pytest.mark.skipif(c))\n" + _BODY
    )
    assert "newly marked" in _sole_finding(str_old, str_new=str_new)


@pytest.mark.parametrize(
    "tuple_case",
    [
        ("def test_a(*skip):", "skip()"),
        ("def test_a(**skip):", "skip()"),
        ("def test_a(pytest):", "pytest.skip()"),
    ],
    ids=["vararg", "kwarg", "pytest-param"],
)
def test_a_star_or_pytest_named_parameter_shadows_the_name(tuple_case: tuple[str, str]) -> None:
    """Review of #1340: ``*skip``, ``**skip`` and a parameter named ``pytest`` shadow the table."""
    str_signature, str_call = tuple_case
    str_old = "def test_a():\n" + _BODY
    str_new = str_signature + f"\n    {str_call}\n" + _BODY
    assert _findings(str_old, str_new=str_new) == []


def test_a_nested_def_named_skip_shadows_pytest_skip() -> None:
    """Review of #1340: a ``def skip()`` inside the test is a helper."""
    str_old = "def test_a():\n" + _BODY
    str_new = "def test_a():\n    def skip():\n        pass\n\n    skip()\n" + _BODY
    assert _findings(str_old, str_new=str_new) == []


@pytest.mark.parametrize(
    "str_head",
    [
        "try:\n    from pytest import skip\nexcept ImportError:\n    from helpers import skip\n",
        "try:\n    from helpers import skip\nexcept ImportError:\n    from pytest import skip\n",
    ],
    ids=["pytest-first", "pytest-last"],
)
def test_a_skip_bound_to_pytest_in_any_arm_stays_pytests(str_head: str) -> None:
    """Review of #1340: arms are alternatives; a pytest binding in one is not erased by another."""
    str_old = "def test_a():\n" + _BODY
    str_new = str_head + "\n\ndef test_a():\n    skip()\n" + _BODY
    assert "newly marked skip" in _sole_finding(str_old, str_new=str_new)


def test_an_xfail_raises_tuple_that_gains_a_type_is_not_a_reorder() -> None:
    """Review of #1340: sorting the tuple must not hide a changed set of types."""
    str_old = "@pytest.mark.xfail(raises=(A,))\ndef test_a():\n" + _BODY
    str_new = "@pytest.mark.xfail(raises=(A, B))\ndef test_a():\n" + _BODY
    assert "newly marked xfail" in _sole_finding(str_old, str_new=str_new)


def test_a_try_import_of_pytest_skip_inside_a_test_stays_pytest() -> None:
    """Review of #1340: an arm that imports pytest's ``skip`` outlives the later arm."""
    str_old = "def test_a():\n" + _BODY
    str_head = (
        "    try:\n        from pytest import skip\n"
        "    except ImportError:\n        from helpers import skip\n"
    )
    str_new = "def test_a():\n" + str_head + "    skip()\n" + _BODY
    assert "newly marked" in _sole_finding(str_old, str_new=str_new)


def test_a_try_that_imports_a_different_name_re_reports_the_except_skip() -> None:
    """Review of #1340: ``from foo import a`` becoming ``from foo import b`` changes the guard."""
    str_tail = "except ImportError:\n        pytest.skip()\n"
    str_old = "def test_a():\n    try:\n        from foo import a\n    " + str_tail + _BODY
    str_new = "def test_a():\n    try:\n        from foo import b\n    " + str_tail + _BODY
    assert "newly marked" in _sole_finding(str_old, str_new=str_new)


def test_a_raise_added_to_a_try_body_re_reports_the_except_skip() -> None:
    """Review of #1340: ``try: f(1)`` gaining ``raise E`` makes the handler fire every run."""
    str_tail = "    except E:\n        pytest.skip()\n"
    str_old = "def test_a():\n    try:\n        f(1)\n" + str_tail + _BODY
    str_new = "def test_a():\n    try:\n        f(1)\n        raise E\n" + str_tail + _BODY
    assert "newly marked" in _sole_finding(str_old, str_new=str_new)


def test_a_skip_called_before_a_local_rebind_is_still_reported() -> None:
    """Review of #1340: ``skip(); skip = helper`` skips for real, as main reported."""
    str_old = "def test_a():\n" + _BODY
    str_new = "def test_a():\n    from pytest import skip\n    skip()\n    skip = helper\n" + _BODY
    assert "newly marked" in _sole_finding(str_old, str_new=str_new)


def test_a_pytest_mark_bound_to_a_name_keeps_the_receiver_agnostic_check() -> None:
    """Review of #1340: ``m = pytest.mark`` then ``applymarker(m.skip)`` is reported."""
    str_old = "def test_a():\n" + _BODY
    str_new = "m = pytest.mark\n\ndef test_a(request):\n    request.applymarker(m.skip)\n" + _BODY
    assert "newly marked" in _sole_finding(str_old, str_new=str_new)


def test_a_skip_rebound_inside_a_loop_is_still_reported() -> None:
    """Review of #1340: a rebind that only some passes of a loop run leaves the call pytest's."""
    str_old = "def test_a():\n" + _BODY
    str_loop = "    for _ in range(2):\n        if c:\n            skip = helper\n        skip()\n"
    str_new = "def test_a():\n    from pytest import skip\n" + str_loop + _BODY
    assert "newly marked" in _sole_finding(str_old, str_new=str_new)


@pytest.mark.parametrize(
    "str_code",
    [
        "from pytest import skip\n    skip(); skip = helper\n",
        "from pytest import skip as s\n    s()\n    s = helper\n",
        "from pytest import skip\n    if c:\n        skip = helper\n    skip()\n",
    ],
    ids=["same-line", "local-alias", "conditional"],
)
def test_a_skip_that_a_local_rebind_may_not_reach_is_still_reported(str_code: str) -> None:
    """Review of #1340: main reported each of these, so the scoping must not hide them."""
    str_old = "def test_a():\n" + _BODY
    str_new = "def test_a():\n    " + str_code + _BODY
    assert "newly marked" in _sole_finding(str_old, str_new=str_new)


def test_a_from_pytest_mark_alias_keeps_the_receiver_agnostic_check() -> None:
    """Review of #1340: ``m = mark`` after ``from pytest import mark`` is an alias of the mark."""
    str_old = "def test_a():\n" + _BODY
    str_head = "from pytest import mark\nm = mark\n\n"
    str_new = str_head + "def test_a(request):\n    request.applymarker(m.skip)\n" + _BODY
    assert "newly marked" in _sole_finding(str_old, str_new=str_new)


def test_a_try_body_without_calls_keeps_the_digest_key() -> None:
    """Review of #1340: ``try: x = d[a]`` becoming ``d[b]`` re-reports its ``except``."""
    str_tail = "    except KeyError:\n        pytest.skip()\n"
    str_old = "def test_a():\n    try:\n        x = d[a]\n" + str_tail + _BODY
    str_new = "def test_a():\n    try:\n        x = d[b]\n" + str_tail + _BODY
    assert "newly marked" in _sole_finding(str_old, str_new=str_new)


_MODULE_CASES = {
    "default": ("", False),
    "import-pytest-alias": ("import pytest as pt\n", False),
    "from-pytest-skip": ("from pytest import skip as s\n", False),
    "from-pytest-mark": ("from pytest import mark\n", False),
    "top-level-helper": ("from helpers import skip\n", False),
    "top-level-def": ("def skip():\n    pass\n", False),
    "top-level-assign": ("skip = helper\n", False),
    "explicit-then-nested-helper": (
        "from pytest import skip\nif X:\n    from helpers import skip\n",
        False,
    ),
    "explicit-then-nested-def": (
        "from pytest import skip\nif X:\n    def skip():\n        pass\n",
        False,
    ),
    "nested-assign": ("if X:\n    skip = helper\n", False),
    "with-def": ("with ctx():\n    def skip():\n        pass\n", False),
    "try-helper": ("try:\n    from helpers import skip\nexcept ImportError:\n    pass\n", True),
    "if-helper": ("if X:\n    from helpers import skip\n", True),
}

_FUNCTION_CASES = {
    "plain": ("def test_a():\n    skip()\n", False),
    "param": ("def test_a(skip):\n    skip()\n", True),
    "vararg": ("def test_a(*skip):\n    skip()\n", True),
    "sole-nested-def": ("def test_a():\n    def skip():\n        pass\n    skip()\n", True),
    "sole-local-import": ("def test_a():\n    from helpers import skip\n    skip()\n", True),
    "call-then-rebind": ("def test_a():\n    skip()\n    skip = helper\n", False),
    "same-line-rebind": ("def test_a():\n    skip(); skip = helper\n", False),
    "conditional-rebind": ("def test_a():\n    if c:\n        skip = helper\n    skip()\n", False),
    "loop-rebind": ("def test_a():\n    for _ in r:\n        skip = helper\n    skip()\n", False),
    "import-then-def": (
        "def test_a():\n    from helpers import skip\n    def skip():\n        pass\n",
        False,
    ),
    "try-local-import": (
        "def test_a():\n    try:\n        from helpers import skip\n"
        "    except ImportError:\n        pass\n    skip()\n",
        False,
    ),
    "local-pytest-import": ("def test_a():\n    from pytest import skip as s\n    s()\n", False),
}

_RECEIVER_CASES = {
    "pytest-mark": ("import pytest\nx = pytest.mark\n", "pytest.mark", False),
    "assigned-alias": ("import pytest\nm = pytest.mark\n", "m", False),
    "from-pytest-mark": ("from pytest import mark\nm = mark\n", "m", False),
    "imported-mark": ("from pytest import mark\n", "mark", False),
    "parameter": ("def f(m):\n    pass\n", "m", False),
    "call-result": ("", "get()", False),
    "foreign-name": ("", "other", True),
}


def _main_names(cls_tree: ast.Module) -> dict[str, str]:
    """Return the name table the checker read on main: direct module statements only.

    Parameters
    ----------
    cls_tree : ast.Module
        The parsed file.

    Returns
    -------
    dict[str, str]
        Every statement nested in ``try``/``if``/``with`` was ignored, and so was every name
        a function bound.
    """
    dict_names = dict(gate._DEFAULT_NAMES)
    list(map(partial(gate._bind_names, dict_names=dict_names), ast.iter_child_nodes(cls_tree)))
    return dict_names


def _kept(dict_main: dict[str, str], *, dict_branch: dict[str, str]) -> bool:
    """Return whether the branch table keeps every binding the main table has.

    Parameters
    ----------
    dict_main : dict[str, str]
        What main recognised.
    dict_branch : dict[str, str]
        What this branch recognises.

    Returns
    -------
    bool
        ``True`` when each pytest name main reports is still reported with the same function.
    """
    return all(dict_branch.get(str_k) == str_v for str_k, str_v in dict_main.items())


@pytest.mark.parametrize("str_case", sorted(_MODULE_CASES))
def test_the_module_name_table_never_loses_a_binding_main_had_except_the_listed_shapes(
    str_case: str,
) -> None:
    """Differential, #1340: the branch may drop a pytest name main kept only for a listed shape."""
    str_source, is_listed = _MODULE_CASES[str_case]
    cls_tree = ast.parse(str_source)
    is_kept = _kept(_main_names(cls_tree), dict_branch=gate._pytest_names(cls_tree))
    assert is_kept is not is_listed


@pytest.mark.parametrize("str_case", sorted(_FUNCTION_CASES))
def test_the_local_name_table_never_loses_a_binding_the_module_had_except_the_listed_shapes(
    str_case: str,
) -> None:
    """Differential, #1340: inside a test, only a parameter or a sole definition may shadow."""
    str_source, is_listed = _FUNCTION_CASES[str_case]
    cls_tree = ast.parse(str_source)
    dict_module = gate._pytest_names(ast.parse(""))
    dict_local = gate._local_names(cls_tree.body[0], dict_names=dict_module)
    assert _kept(_main_names(ast.parse("")), dict_branch=dict_local) is not is_listed


@pytest.mark.parametrize("str_case", sorted(_RECEIVER_CASES))
def test_a_marker_receiver_is_accepted_as_on_main_except_the_listed_shape(str_case: str) -> None:
    """Differential, #1340: only a receiver rooted at a name nothing assigns is not a mark."""
    str_source, str_receiver, is_listed = _RECEIVER_CASES[str_case]
    dict_names = gate._pytest_names(ast.parse(str_source))
    cls_expr = ast.parse(str_receiver, mode="eval").body
    assert gate._is_pytest_mark(cls_expr, dict_names=dict_names) is not is_listed


def test_a_later_local_import_of_another_name_does_not_erase_an_earlier_skip() -> None:
    """Review of #1340: a later ``import mark as skip`` leaves the earlier ``skip()`` pytest's."""
    str_old = "def test_a():\n" + _BODY
    str_head = "def test_a():\n    from pytest import skip\n    skip()\n"
    str_new = str_head + "    from pytest import mark as skip\n" + _BODY
    assert "newly marked" in _sole_finding(str_old, str_new=str_new)


def test_a_match_capture_bound_to_pytest_mark_keeps_the_receiver_check() -> None:
    """Review of #1340: ``case m:`` on ``pytest.mark`` binds ``m``, so ``m.skip`` is a mark."""
    str_old = "def test_a():\n" + _BODY
    str_head = "import pytest\n\nmatch pytest.mark:\n    case m:\n        pass\n\n"
    str_new = str_head + "def test_a(request):\n    request.applymarker(m.skip)\n" + _BODY
    assert "newly marked" in _sole_finding(str_old, str_new=str_new)


def test_a_star_import_from_pytest_keeps_the_receiver_check_open() -> None:
    """Review of #1340: ``from pytest import *`` binds ``mark``, so ``mark.skip`` is a skip."""
    str_head = "from pytest import *\n\ndef test_a(request):\n"
    str_old = str_head + "    assert 1 == 1\n"
    str_new = str_head + "    request.applymarker(mark.skip)\n    assert 1 == 1\n"
    assert "newly marked" in _sole_finding(str_old, str_new=str_new)


def test_a_lambda_parameter_in_a_default_does_not_hide_pytest_from_the_body() -> None:
    """Review of #1340: ``lambda pytest: 0`` in a default is not a parameter of the test."""
    str_head = "import pytest\n\ndef test_a(f=lambda pytest: 0):\n"
    str_old = str_head + "    assert 1 == 1\n"
    str_new = str_head + "    pytest.skip()\n    assert 1 == 1\n"
    assert "newly marked" in _sole_finding(str_old, str_new=str_new)


@pytest.mark.parametrize(
    ("str_before", "str_after"),
    [
        ("f(url)", 'f("invalid://")'),
        ('import_module("a")', 'import_module("b")'),
        ("f(strict=True)", "f(strict=False)"),
    ],
)
def test_an_edited_non_numeric_try_argument_under_an_unchanged_except_skip_is_reported(
    *, str_before: str, str_after: str
) -> None:
    """Review of #1340: a new argument can make the handler fire every run, so it is a finding."""
    str_tail = "    except E:\n        pytest.skip()\n" + _BODY
    str_old = f"def test_a():\n    try:\n        {str_before}\n" + str_tail
    str_new = f"def test_a():\n    try:\n        {str_after}\n" + str_tail
    assert "newly marked" in _sole_finding(str_old, str_new=str_new)


def test_an_alias_receiver_is_reported_when_the_name_table_has_no_assigned_entry() -> None:
    """Review of #1340: a table without ``<assigned>`` must read a receiver as possibly a mark."""
    cls_call = ast.parse("request.applymarker(m.skip)").body[0].value
    assert gate._skip_call_name(cls_call) == "applymarker-skip"


def test_a_called_mark_import_is_not_a_skip() -> None:
    """Review of #1340: ``mark`` is bound from pytest but is not a run-time outcome function."""
    str_old = "def test_a():\n" + _BODY
    str_new = "from pytest import mark\n\ndef test_a():\n    mark('x')\n" + _BODY
    assert _findings(str_old, str_new=str_new) == []


def test_xfail_raises_single_tuple_equals_the_bare_type() -> None:
    """Review of #1340: ``raises=A`` and ``raises=(A,)`` name the same type."""
    str_old = "@pytest.mark.xfail(raises=A)\ndef test_a():\n" + _BODY
    str_new = "@pytest.mark.xfail(raises=(A,))\ndef test_a():\n" + _BODY
    assert _findings(str_old, str_new=str_new) == []


def test_an_async_def_in_a_test_body_shadows_pytest() -> None:
    """Review of #1340: an ``async def pytest`` in a test body makes ``pytest`` a local name."""
    str_old = "import pytest\n\ndef test_a():\n" + _BODY
    str_head = "import pytest\n\ndef test_a():\n    async def pytest():\n        pass\n"
    str_new = str_head + "    pytest.skip()\n" + _BODY
    assert _findings(str_old, str_new=str_new) == []


@pytest.mark.parametrize(
    "str_head",
    [
        "def test_a(skip=pytest.skip):\n    skip()\n",
        "def test_a(*, skip=pytest.skip):\n    skip()\n",
        "def test_a(pytest=pytest):\n    pytest.skip()\n",
    ],
)
def test_a_parameter_with_a_default_does_not_hide_a_skip(str_head: str) -> None:
    """Review of #1340: a defaulted parameter is not a fixture, so its call still skips."""
    str_def = str_head.split("\n", 1)[0]
    str_old = "import pytest\n\n" + str_def + "\n    pass\n" + _BODY
    str_new = "import pytest\n\n" + str_head + _BODY
    assert "newly marked" in _sole_finding(str_old, str_new=str_new)


@pytest.mark.parametrize("str_module", ["_pytest.outcomes", "_pytest.mark"])
def test_a_local_import_from_pytest_internals_is_still_pytests_skip(str_module: str) -> None:
    """Review of #1340: ``from _pytest.outcomes import skip`` is pytest's own, not a helper."""
    str_old = "def test_a():\n" + _BODY
    str_new = f"def test_a():\n    from {str_module} import skip\n    skip()\n" + _BODY
    assert "newly marked" in _sole_finding(str_old, str_new=str_new)


def test_an_edited_subscript_under_an_unchanged_except_skip_is_reported() -> None:
    """Review of #1340: a non-call statement in the ``try`` body is guarded too."""
    str_tail = "    except KeyError:\n        pytest.skip()\n" + _BODY
    str_head = "def test_a():\n    try:\n        cfg = load()\n        v = cfg['"
    str_old = str_head + "k']\n" + str_tail
    str_new = str_head + "missing']\n" + str_tail
    assert "newly marked" in _sole_finding(str_old, str_new=str_new)


def test_a_connect_timeout_edited_to_zero_under_an_unchanged_except_skip_is_reported() -> None:
    """Owner decision on #1340: ``timeout=5`` to ``timeout=0`` can make the handler always fire."""
    str_tail = "    except E:\n        pytest.skip()\n" + _BODY
    str_old = "def test_a():\n    try:\n        connect(timeout=5)\n" + str_tail
    str_new = "def test_a():\n    try:\n        connect(timeout=0)\n" + str_tail
    assert "newly marked" in _sole_finding(str_old, str_new=str_new)


def test_a_nested_def_that_wraps_pytest_skip_does_not_hide_the_skip() -> None:
    """Review of #1340: main reports ``skip()``; a wrapper around ``pytest.skip`` still skips."""
    str_old = "import pytest\n\ndef test_a():\n" + _BODY
    str_head = "import pytest\n\ndef test_a():\n    def skip():\n        pytest.skip()\n"
    assert "newly marked" in _sole_finding(str_old, str_new=str_head + "    skip()\n" + _BODY)


@pytest.mark.parametrize(
    ("str_import", "str_call"),
    [("import pytest as pt", "pt.skip()"), ("from pytest import skip as s", "s()")],
)
def test_a_nested_def_wrapping_an_aliased_skip_does_not_hide_the_skip(
    *, str_import: str, str_call: str
) -> None:
    """Review of #1340: main reports ``skip()``; a wrapper over an aliased skip still skips."""
    str_old = f"{str_import}\n\ndef test_a():\n" + _BODY
    str_head = f"{str_import}\n\ndef test_a():\n    def skip():\n        {str_call}\n"
    assert "newly marked" in _sole_finding(str_old, str_new=str_head + "    skip()\n" + _BODY)


def test_a_foreign_nested_import_after_a_pytest_star_import_keeps_skip_pytests() -> None:
    """Review of #1340: after ``from pytest import *``, a nested foreign ``skip`` stays pytest."""
    str_head = "from pytest import *\n"
    str_mid = "try:\n    from helpers import skip\nexcept ImportError:\n    pass\n\n"
    str_old = str_head + str_mid + "def test_a():\n" + _BODY
    str_new = str_head + str_mid + "def test_a():\n    skip()\n" + _BODY
    assert "newly marked" in _sole_finding(str_old, str_new=str_new)


def test_a_skip_added_to_a_second_try_with_the_same_body_is_reported() -> None:
    """#1343: two ``try`` blocks with one body and one caught type must keep distinct labels."""
    str_head = "def test_a():\n    try:\n        f()\n    except E:\n        pytest.skip()\n"
    str_second = "    try:\n        f()\n    except E:\n        "
    str_old = str_head + str_second + "pass\n" + _BODY
    str_new = str_head + str_second + "pytest.skip()\n" + _BODY
    assert "newly marked" in _sole_finding(str_old, str_new=str_new)


def test_a_module_try_key_ignores_an_edit_in_a_handler_of_the_same_statement() -> None:
    """#1343: module and test-body ``try`` keys cover the body only, so a handler edit is quiet."""
    str_head = "import pytest\n\ntry:\n    import x\nexcept ImportError:\n    y = 1\n"
    str_tail = "except KeyError:\n    pytestmark = pytest.mark.skip\n\ndef test_a():\n" + _BODY
    assert (
        _findings(str_head + str_tail, str_new=str_head.replace("y = 1", "y = 2") + str_tail) == []
    )


def test_a_late_skipif_with_a_guard_ending_in_a_call_has_no_unguarded_condition() -> None:
    """#1343: a guard ending in a call makes the label guarded, so it has no condition."""
    assert gate._marker_condition("applymarker-skipif:c(if):is_ci()") is None


def test_a_local_skip_import_wins_over_a_module_binding_of_the_same_name() -> None:
    """#1343: ``from pytest import skip as s`` in a test beats a module ``mark as s``."""
    str_head = "from pytest import mark as s\n\ndef test_a():\n"
    str_old = str_head + _BODY
    str_new = str_head + "    from pytest import skip as s\n    s()\n" + _BODY
    assert "newly marked" in _sole_finding(str_old, str_new=str_new)


def test_a_name_table_without_the_assigned_entry_stays_without_it_in_a_test_body() -> None:
    """#1343: ``_local_names`` adds ``<assigned>`` only when the table it extends has it."""
    cls_fn = ast.parse("def test_a():\n    pass\n").body[0]
    assert gate._KEY_ASSIGNED not in gate._local_names(cls_fn, dict_names=gate._DEFAULT_NAMES)


def test_a_skip_added_to_a_second_identical_module_try_is_reported() -> None:
    """Review of #1346: two module ``try`` blocks with one body keep distinct labels."""
    str_try = "try:\n    next(items)\nexcept StopIteration:\n    "
    str_head = "import pytest\n\n" + str_try + "pytestmark = pytest.mark.skip\n" + str_try
    str_old = str_head + "pass\n\ndef test_a():\n" + _BODY
    str_new = str_head + "pytestmark = pytest.mark.skip\n\ndef test_a():\n" + _BODY
    assert "newly marked" in _sole_finding(str_old, str_new=str_new)
