"""Unit tests for the DataFrame/Series relabelling helpers."""

import pytest

from src.utils.frames import from_cursor, map_with_default


def test_map_with_default_relabels_known_and_defaults_unknown() -> None:
	"""Known values are mapped; every unmapped value goes to the default."""
	pd = pytest.importorskip("pandas")
	series_in = pd.Series(["a", "b", "z", None])
	series_out = map_with_default(series_in, {"a": 1, "b": 2}, default=-1)
	assert list(series_out) == [1, 2, -1, -1]


def test_map_with_default_is_total_no_nan_leak() -> None:
	"""No output cell is NaN — an unmapped value can never leak through."""
	pd = pytest.importorskip("pandas")
	series_in = pd.Series(["x", "y"])
	series_out = map_with_default(series_in, {"x": "ok"}, default="other")
	assert not series_out.isna().any()
	assert list(series_out) == ["ok", "other"]


class _FakeCursor:
	"""Minimal DB-API cursor stand-in: a description plus rows.

	Parameters
	----------
	description : list or None
		The DB-API ``description`` sequence, or ``None`` for a non-returning statement.
	list_rows : list
		Rows returned by ``fetchall``.
	"""

	def __init__(self, description: list | None, list_rows: list) -> None:
		self.description = description
		self._list_rows = list_rows

	def fetchall(self) -> list:
		"""Return the canned rows.

		Returns
		-------
		list
			The rows this cursor was built with.
		"""
		return self._list_rows


def test_from_cursor_types_every_declared_column() -> None:
	"""Rows are shaped from the cursor description and coerced to the declared dtypes."""
	cls_cursor = _FakeCursor([("id",), ("title",)], [(1, "a"), (2, "b")])
	df_out = from_cursor(cls_cursor, {"id": "int64", "title": "str"})
	assert list(df_out.columns) == ["id", "title"]
	assert str(df_out["id"].dtype) == "int64"
	assert df_out["title"].tolist() == ["a", "b"]


def test_from_cursor_returns_the_declared_columns_when_there_are_no_rows() -> None:
	"""A non-returning cursor yields an EMPTY frame that still has the declared columns.

	A bare empty frame has no columns, so a caller that concatenates or renders the result
	behaves differently depending on whether rows happened to exist — the shape becomes
	data-dependent. Returning the declared columns keeps it constant.
	"""
	cls_cursor = _FakeCursor(None, [])
	df_out = from_cursor(cls_cursor, {"id": "int64", "title": "str"})
	assert df_out.empty
	assert list(df_out.columns) == ["id", "title"]
