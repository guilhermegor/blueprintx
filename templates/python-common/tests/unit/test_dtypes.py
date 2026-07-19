"""Unit tests for the explicit DataFrame typing helper."""

from datetime import date

import pandas as pd
import pytest

from src.utils.dtypes import apply_dtypes


def _make_frame() -> pd.DataFrame:
	return pd.DataFrame(
		{
			"code": [1, 2],
			"amount": ["10", "20"],
			"ref_date": ["2026-01-15", "2026-02-20"],
			"created_at": ["2026-01-15 09:30:00", "2026-02-20 18:45:00"],
		}
	)


def test_apply_dtypes_astype_dict_casts_columns() -> None:
	"""The astype dict casts each listed column to its declared type."""
	df_input = _make_frame()
	df_typed = apply_dtypes(df_input, dict_dtypes={"code": "str", "amount": "float64"})
	assert df_typed["code"].tolist() == ["1", "2"]
	assert df_typed["amount"].tolist() == [10.0, 20.0]


def test_apply_dtypes_str_declaration_keeps_missing_values_na() -> None:
	"""A ``"str"`` declaration must not turn a missing value into the literal ``"nan"``.

	On pandas < 3, ``astype("str")`` renders a missing value as the three-character string
	``"nan"`` and ``.isna()`` then reports ``False`` — a blank source field becomes
	indistinguishable from one the source actually sent, and nothing raises. ``apply_dtypes``
	normalises ``"str"`` to the nullable ``"string"`` dtype, which behaves identically on
	pandas 2 and 3.
	"""
	df_input = pd.DataFrame({"id_subclasse": ["A", float("nan")]})
	df_typed = apply_dtypes(df_input, dict_dtypes={"id_subclasse": "str"})

	assert df_typed["id_subclasse"].isna().tolist() == [False, True]
	# The blank must be gone entirely rather than stored as text.
	assert df_typed["id_subclasse"].dropna().tolist() == ["A"]
	# Elements are still ordinary ``str``, so isinstance assertions keep passing.
	assert isinstance(df_typed["id_subclasse"].iloc[0], str)


def test_apply_dtypes_date_column_coerces_to_date_objects() -> None:
	"""A date column is coerced to pure ``datetime.date`` values."""
	df_typed = apply_dtypes(_make_frame(), list_date_cols=["ref_date"])
	assert df_typed["ref_date"].tolist() == [date(2026, 1, 15), date(2026, 2, 20)]


def test_apply_dtypes_datetime_column_coerces_to_timestamps() -> None:
	"""A datetime column is coerced to a datetime64 dtype."""
	df_typed = apply_dtypes(_make_frame(), list_datetime_cols=["created_at"])
	assert pd.api.types.is_datetime64_any_dtype(df_typed["created_at"])


def test_apply_dtypes_missing_column_raises_key_error() -> None:
	"""Referencing an absent column fails fast with ``KeyError``."""
	with pytest.raises(KeyError):
		apply_dtypes(_make_frame(), dict_dtypes={"nope": "str"})


def test_apply_dtypes_column_in_two_sets_raises_value_error() -> None:
	"""A column assigned two target types fails fast with ``ValueError``."""
	with pytest.raises(ValueError, match="more than one target type"):
		apply_dtypes(
			_make_frame(),
			dict_dtypes={"ref_date": "str"},
			list_date_cols=["ref_date"],
		)


def test_apply_dtypes_does_not_mutate_input_frame() -> None:
	"""The input frame is left unmodified (work happens on a copy)."""
	df_input = _make_frame()
	apply_dtypes(df_input, dict_dtypes={"code": "str"})
	assert df_input["code"].tolist() == [1, 2]
