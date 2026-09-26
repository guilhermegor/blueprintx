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

	assert not map_with_default(series_in, {"x": "ok"}, default="other").isna().any()


def test_map_with_default_sends_the_unmapped_value_to_the_default() -> None:
	"""Totality is the property; THIS is what the unmapped value actually becomes.

	Split rather than folded in (blueprintx#544): "no NaN" would also be satisfied by a
	helper that dropped the unmapped row or substituted something else entirely.
	"""
	pd = pytest.importorskip("pandas")
	series_in = pd.Series(["x", "y"])

	assert list(map_with_default(series_in, {"x": "ok"}, default="other")) == ["ok", "other"]


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


_DICT_DTYPES = {"id": "int64", "title": "str"}
_LIST_RECORDS = [{"id": 1, "title": "a"}, {"id": 2, "title": "b"}]


# ⚠️ ONE BUILD, SEVERAL FACETS — the "expensive shared setup" pattern from tests/CLAUDE.md,
# applied so the one-assert rule does not turn three claims about one frame into three
# rebuilds of it (blueprintx#544). Module-scoped because the frames are only ever read.
@pytest.fixture(scope="module")
def df_from_cursor() -> object:
	"""Shape one populated cursor into a frame, once, for the three tests that inspect it.

	Returns
	-------
	pandas.DataFrame
		The coerced frame.
	"""
	pytest.importorskip("pandas")
	return from_cursor(_FakeCursor([("id",), ("title",)], [(1, "a"), (2, "b")]), _DICT_DTYPES)


@pytest.fixture(scope="module")
def df_from_records() -> object:
	"""Shape the same rows as mappings, once, for the three tests that inspect it.

	Returns
	-------
	pandas.DataFrame
		The coerced frame.
	"""
	pytest.importorskip("pandas")
	return from_records(_LIST_RECORDS, _DICT_DTYPES)


@pytest.mark.parametrize("str_fixture", ["df_from_cursor", "df_from_records"])
def test_every_declared_column_is_present(str_fixture: str, request: pytest.FixtureRequest) -> None:
	"""Both seams shape the frame from the DECLARED columns, in declaration order.

	Parameters
	----------
	str_fixture : str
		Name of the shared-frame fixture under test.
	request : pytest.FixtureRequest
		Used to resolve the fixture by name, so one case list covers both seams.
	"""
	assert list(request.getfixturevalue(str_fixture).columns) == ["id", "title"]


@pytest.mark.parametrize("str_fixture", ["df_from_cursor", "df_from_records"])
def test_every_declared_column_is_coerced_to_its_dtype(
	str_fixture: str, request: pytest.FixtureRequest
) -> None:
	"""Declaring a dtype is only worth anything if the column actually carries it.

	Parameters
	----------
	str_fixture : str
		Name of the shared-frame fixture under test.
	request : pytest.FixtureRequest
		Used to resolve the fixture by name.
	"""
	assert str(request.getfixturevalue(str_fixture)["id"].dtype) == "int64"


@pytest.mark.parametrize("str_fixture", ["df_from_cursor", "df_from_records"])
def test_the_row_values_survive_the_coercion(
	str_fixture: str, request: pytest.FixtureRequest
) -> None:
	"""Shape and dtype are both satisfiable by a frame that lost its data.

	Parameters
	----------
	str_fixture : str
		Name of the shared-frame fixture under test.
	request : pytest.FixtureRequest
		Used to resolve the fixture by name.
	"""
	assert request.getfixturevalue(str_fixture)["title"].tolist() == ["a", "b"]


# A bare empty frame has no columns, so a caller that concatenates or renders the result
# behaves differently depending on whether rows happened to exist — the shape becomes
# data-dependent. Returning the declared columns keeps it constant. Both seams owe the
# property, and each owes BOTH halves of it: empty, and still shaped.
@pytest.fixture(scope="module")
def df_empty_from_cursor() -> object:
	"""Shape a non-returning cursor, once.

	Returns
	-------
	pandas.DataFrame
		The empty-but-shaped frame.
	"""
	pytest.importorskip("pandas")
	return from_cursor(_FakeCursor(None, []), _DICT_DTYPES)


@pytest.fixture(scope="module")
def df_empty_from_records() -> object:
	"""Shape an empty record list, once.

	Returns
	-------
	pandas.DataFrame
		The empty-but-shaped frame.
	"""
	pytest.importorskip("pandas")
	return from_records([], _DICT_DTYPES)


@pytest.mark.parametrize("str_fixture", ["df_empty_from_cursor", "df_empty_from_records"])
def test_no_rows_yields_an_empty_frame(str_fixture: str, request: pytest.FixtureRequest) -> None:
	"""No rows in, no rows out — the declared columns must not fabricate one.

	Parameters
	----------
	str_fixture : str
		Name of the shared empty-frame fixture under test.
	request : pytest.FixtureRequest
		Used to resolve the fixture by name.
	"""
	assert request.getfixturevalue(str_fixture).empty


@pytest.mark.parametrize("str_fixture", ["df_empty_from_cursor", "df_empty_from_records"])
def test_an_empty_frame_still_carries_the_declared_columns(
	str_fixture: str, request: pytest.FixtureRequest
) -> None:
	"""The point of the branch: the shape must not depend on whether rows existed.

	Parameters
	----------
	str_fixture : str
		Name of the shared empty-frame fixture under test.
	request : pytest.FixtureRequest
		Used to resolve the fixture by name.
	"""
	assert list(request.getfixturevalue(str_fixture).columns) == ["id", "title"]


# ⚠️ apply_dtypes requires the column sets to be disjoint, so a date column is declared by
# list_date_cols alone and never also in dict_dtypes.
@pytest.fixture(scope="module")
def tuple_date_col_frames() -> tuple:
	"""Shape the empty and populated date-column frames once, for the pair of tests below.

	Returns
	-------
	tuple of (pandas.DataFrame, pandas.DataFrame)
		The empty-path frame and the populated-path frame.
	"""
	pytest.importorskip("pandas")
	df_empty = from_cursor(_FakeCursor(None, []), {"id": "int64"}, list_date_cols=["dt_ref"])
	df_rows = from_cursor(
		_FakeCursor([("id",), ("dt_ref",)], [(1, "2026-01-31")]),
		{"id": "int64"},
		list_date_cols=["dt_ref"],
	)
	return df_empty, df_rows


def test_the_empty_path_still_declares_the_date_column(tuple_date_col_frames: tuple) -> None:
	"""The date column has to exist at all before its dtype can be compared.

	Parameters
	----------
	tuple_date_col_frames : tuple of (pandas.DataFrame, pandas.DataFrame)
		The shared empty-path and populated-path frames.
	"""
	df_empty, _ = tuple_date_col_frames

	assert "dt_ref" in df_empty.columns


def test_from_cursor_applies_date_columns_on_the_empty_path(
	tuple_date_col_frames: tuple,
) -> None:
	"""An empty result takes the SAME coercion path as a populated one.

	Omitting ``list_date_cols`` on the empty branch gives a date column a different dtype
	depending on whether rows happened to exist — reintroducing, one argument down, the very
	data-dependent shape the declared-columns branch exists to prevent.

	Parameters
	----------
	tuple_date_col_frames : tuple of (pandas.DataFrame, pandas.DataFrame)
		The shared empty-path and populated-path frames.
	"""
	df_empty, df_rows = tuple_date_col_frames

	assert str(df_empty["dt_ref"].dtype) == str(df_rows["dt_ref"].dtype)
