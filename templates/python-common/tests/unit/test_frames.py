"""Unit tests for the DataFrame/Series relabelling helpers."""

import pytest

from src.utils.frames import from_cursor, from_records, map_with_default


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

    The ``description`` attribute keeps its bare DB-API name on purpose — the seam looks it
    up by exactly that spelling, so renaming it would break the double.

    Parameters
    ----------
    list_description : list or None
            The DB-API ``description`` sequence, or ``None`` for a non-returning statement.
    list_rows : list
            Rows returned by ``fetchall``.
    """

    def __init__(self, list_description: list | None, list_rows: list) -> None:
        self.description = list_description
        self.list_rows = list_rows

    def fetchall(self) -> list:
        """Return the canned rows.

        Returns
        -------
        list
                The rows this cursor was built with.
        """
        return self.list_rows


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


def test_from_records_types_every_declared_column() -> None:
    """Row mappings are shaped and coerced to the declared dtypes."""
    list_records = [{"id": 1, "title": "a"}, {"id": 2, "title": "b"}]
    df_out = from_records(list_records, {"id": "int64", "title": "str"})
    assert list(df_out.columns) == ["id", "title"]
    assert str(df_out["id"].dtype) == "int64"
    assert df_out["title"].tolist() == ["a", "b"]


def test_from_records_returns_the_declared_columns_when_empty() -> None:
    """No rows still yields the declared columns, so the shape is not data-dependent."""
    df_out = from_records([], {"id": "int64", "title": "str"})
    assert df_out.empty
    assert list(df_out.columns) == ["id", "title"]


def test_from_cursor_applies_date_columns_on_the_empty_path() -> None:
    """An empty result takes the SAME coercion path as a populated one.

    Omitting ``list_date_cols`` on the empty branch gives a date column a different dtype
    depending on whether rows happened to exist — reintroducing, one argument down, the very
    data-dependent shape the declared-columns branch exists to prevent.
    """
    # apply_dtypes requires the column sets to be disjoint, so a date column is declared by
    # list_date_cols alone and never also in dict_dtypes.
    cls_cursor = _FakeCursor(None, [])
    df_out = from_cursor(cls_cursor, {"id": "int64"}, list_date_cols=["dt_ref"])
    assert "dt_ref" in df_out.columns

    cls_populated = _FakeCursor([("id",), ("dt_ref",)], [(1, "2026-01-31")])
    df_rows = from_cursor(cls_populated, {"id": "int64"}, list_date_cols=["dt_ref"])
    # The empty and populated results agree on the date column's dtype.
    assert str(df_out["dt_ref"].dtype) == str(df_rows["dt_ref"].dtype)
