"""Unit tests for the scope-filter kill-switch reference pattern (blueprintx#161).

Freezes the measured-price contract: an active filter must report the exact rows
dropped alongside the before/after counts, and an unset or garbled kill switch must
resolve to the caller's safe-side default rather than silently reverting to the
expensive side. Revert either guard in ``src/model/scope_filter_example.py`` and
``test_apply_scope_filter_measures_the_price_when_active`` or
``test_resolve_kill_switch_unrecognised_token_falls_back_to_default`` goes red.
"""

import pandas as pd
import pytest

from model.scope_filter_example import apply_scope_filter, resolve_kill_switch


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


def test_apply_scope_filter_measures_the_price_when_active(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""Frozen price: 5 rows in, 3 belong to the excluded classes, 2 must remain."""
	monkeypatch.setenv(_ENV_VAR, "true")
	df_input = pd.DataFrame(
		{
			"fund_class": ["FII", "FIDC", "Ações", "Ações", "FIP"],
			"id": [1, 2, 3, 4, 5],
		}
	)
	df_output, cls_price = apply_scope_filter(
		df_input,
		str_column="fund_class",
		set_excluded_values=frozenset({"FII", "FIDC", "FIP"}),
		str_env_var=_ENV_VAR,
		bool_default_exclude=False,
	)
	assert cls_price.int_rows_before == 5
	assert cls_price.int_rows_after == 2
	assert cls_price.int_rows_dropped == 3
	assert cls_price.bool_filter_active is True
	assert list(df_output["fund_class"]) == ["Ações", "Ações"]


def test_apply_scope_filter_is_a_noop_when_switch_is_off(
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""Kill switch off: not one row is dropped, and the price says so."""
	monkeypatch.setenv(_ENV_VAR, "false")
	df_input = pd.DataFrame({"fund_class": ["FII", "Ações"], "id": [1, 2]})
	df_output, cls_price = apply_scope_filter(
		df_input,
		str_column="fund_class",
		set_excluded_values=frozenset({"FII"}),
		str_env_var=_ENV_VAR,
		bool_default_exclude=False,
	)
	assert cls_price.int_rows_dropped == 0
	assert cls_price.bool_filter_active is False
	assert len(df_output) == 2
