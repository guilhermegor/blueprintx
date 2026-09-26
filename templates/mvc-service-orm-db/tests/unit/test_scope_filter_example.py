"""Unit tests for the scope-filter kill-switch reference pattern (blueprintx#161).

Freezes the measured-price contract: an active filter must report the exact rows
dropped alongside the before/after counts, and an unset or garbled kill switch must
resolve to the caller's safe-side default rather than silently reverting to the
expensive side. Revert either guard in ``src/model/scope_filter_example.py`` and
``test_active_filter_freezes_each_price_count`` or
``test_resolve_kill_switch_unrecognised_token_falls_back_to_default`` goes red.

Each test asserts exactly once (blueprintx#544): the two frozen scenarios are built once
per test by the ``tuple_active_run`` / ``tuple_inactive_run`` fixtures, and the three
price counts of an active run are one parametrized assertion over different attributes
rather than three copies of the same setup.
"""

import pandas as pd
import pytest

from model.scope_filter_example import ScopeFilterPrice, apply_scope_filter, resolve_kill_switch


_ENV_VAR = "SCOPE_FILTER_EXCLUDE_TEST"


def test_resolve_kill_switch_unset_falls_back_to_default(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""An unset variable resolves to the caller's safe-side default, never a hard True."""
	monkeypatch.delenv(_ENV_VAR, raising=False)
	assert resolve_kill_switch(_ENV_VAR, bool_default=False) is False


def test_resolve_kill_switch_unrecognised_token_falls_back_to_default(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""A garbled token (``"blah"``) resolves to the safe default, never silently to True."""
	monkeypatch.setenv(_ENV_VAR, "blah")
	assert resolve_kill_switch(_ENV_VAR, bool_default=False) is False


def test_resolve_kill_switch_recognised_token_wins(monkeypatch: pytest.MonkeyPatch) -> None:
	"""A recognised token overrides the default in either direction."""
	monkeypatch.setenv(_ENV_VAR, "yes")
	assert resolve_kill_switch(_ENV_VAR, bool_default=False) is True


@pytest.fixture
def tuple_active_run(
	monkeypatch: pytest.MonkeyPatch,
) -> tuple[pd.DataFrame, ScopeFilterPrice]:
	"""Frozen scenario, switch ON: 5 rows in, 3 belong to the excluded classes, 2 must remain."""
	monkeypatch.setenv(_ENV_VAR, "true")
	df_input = pd.DataFrame(
		{
			"fund_class": ["FII", "FIDC", "Ações", "Ações", "FIP"],
			"id": [1, 2, 3, 4, 5],
		}
	)
	return apply_scope_filter(
		df_input,
		str_column="fund_class",
		set_excluded_values=frozenset({"FII", "FIDC", "FIP"}),
		str_env_var=_ENV_VAR,
		bool_default_exclude=False,
	)


@pytest.fixture
def tuple_inactive_run(
	monkeypatch: pytest.MonkeyPatch,
) -> tuple[pd.DataFrame, ScopeFilterPrice]:
	"""Frozen scenario, switch OFF: 2 rows in, one of them an excluded class, nothing dropped."""
	monkeypatch.setenv(_ENV_VAR, "false")
	df_input = pd.DataFrame({"fund_class": ["FII", "Ações"], "id": [1, 2]})
	return apply_scope_filter(
		df_input,
		str_column="fund_class",
		set_excluded_values=frozenset({"FII"}),
		str_env_var=_ENV_VAR,
		bool_default_exclude=False,
	)


@pytest.mark.parametrize(
	("str_attribute", "int_expected"),
	[("int_rows_before", 5), ("int_rows_after", 2), ("int_rows_dropped", 3)],
)
def test_active_filter_freezes_each_price_count(
	tuple_active_run: tuple[pd.DataFrame, ScopeFilterPrice],
	str_attribute: str,
	int_expected: int,
) -> None:
	"""Each measured count of an active run is frozen at its own value."""
	assert getattr(tuple_active_run[1], str_attribute) == int_expected


def test_active_filter_reports_itself_as_active(
	tuple_active_run: tuple[pd.DataFrame, ScopeFilterPrice],
) -> None:
	"""An active run says so in the price, so a silent no-op cannot pass for a filter."""
	assert tuple_active_run[1].bool_filter_active is True


def test_active_filter_keeps_only_the_unexcluded_rows(
	tuple_active_run: tuple[pd.DataFrame, ScopeFilterPrice],
) -> None:
	"""The surviving frame holds exactly the rows outside the excluded classes."""
	assert list(tuple_active_run[0]["fund_class"]) == ["Ações", "Ações"]


def test_inactive_filter_drops_no_row(
	tuple_inactive_run: tuple[pd.DataFrame, ScopeFilterPrice],
) -> None:
	"""Kill switch off: the measured price reports not one row dropped."""
	assert tuple_inactive_run[1].int_rows_dropped == 0


def test_inactive_filter_reports_itself_as_inactive(
	tuple_inactive_run: tuple[pd.DataFrame, ScopeFilterPrice],
) -> None:
	"""Kill switch off: the price says the filter never ran."""
	assert tuple_inactive_run[1].bool_filter_active is False


def test_inactive_filter_returns_the_frame_untouched(
	tuple_inactive_run: tuple[pd.DataFrame, ScopeFilterPrice],
) -> None:
	"""Kill switch off: every input row is still in the returned frame."""
	assert len(tuple_inactive_run[0]) == 2
