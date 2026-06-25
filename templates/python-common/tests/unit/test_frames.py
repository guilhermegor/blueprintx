"""Unit tests for the DataFrame/Series relabelling helpers."""

import pytest

from src.utils.frames import map_with_default


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
