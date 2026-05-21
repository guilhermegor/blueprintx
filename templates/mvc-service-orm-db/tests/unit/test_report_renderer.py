"""Unit tests for the RenderToExcel view.

Validates that the view writes a DataFrame to an ``.xlsx`` file, creates any
missing parent directories, returns the written path, and round-trips data.
The ``df_sample`` fixture is provided by ``conftest.py``.
"""

from pathlib import Path

import pandas as pd
from pytest_mock import MockerFixture

from src.view.report_renderer import RenderToExcel


# --------------------------
# Tests
# --------------------------
def test_render_writes_file_to_disk(df_sample: pd.DataFrame, tmp_path: Path) -> None:
	"""The rendered ``.xlsx`` file exists on disk after render.

	Parameters
	----------
	df_sample : pd.DataFrame
		Sample data to render.
	tmp_path : pathlib.Path
		Pytest-provided temporary directory.

	Returns
	-------
	None
	"""
	path_out = tmp_path / "report.xlsx"
	RenderToExcel(path_out).render(df_sample)
	assert path_out.exists()


def test_render_returns_written_path(df_sample: pd.DataFrame, tmp_path: Path) -> None:
	"""``render()`` returns the path it wrote to.

	Parameters
	----------
	df_sample : pd.DataFrame
		Sample data to render.
	tmp_path : pathlib.Path
		Pytest-provided temporary directory.

	Returns
	-------
	None
	"""
	path_out = tmp_path / "report.xlsx"
	path_result = RenderToExcel(path_out).render(df_sample)
	assert path_result == path_out


def test_render_missing_parent_dir_creates_it(df_sample: pd.DataFrame, tmp_path: Path) -> None:
	"""``render()`` creates parent directories that do not yet exist.

	Parameters
	----------
	df_sample : pd.DataFrame
		Sample data to render.
	tmp_path : pathlib.Path
		Pytest-provided temporary directory.

	Returns
	-------
	None
	"""
	path_out = tmp_path / "nested" / "deep" / "report.xlsx"
	RenderToExcel(path_out).render(df_sample)
	assert path_out.exists()


def test_render_roundtrip_preserves_data(df_sample: pd.DataFrame, tmp_path: Path) -> None:
	"""Data read back from the rendered file matches the input.

	Parameters
	----------
	df_sample : pd.DataFrame
		Sample data to render.
	tmp_path : pathlib.Path
		Pytest-provided temporary directory.

	Returns
	-------
	None
	"""
	path_out = tmp_path / "report.xlsx"
	RenderToExcel(path_out).render(df_sample)
	df_read = pd.read_excel(path_out, engine="openpyxl")
	pd.testing.assert_frame_equal(df_read, df_sample)


def test_render_uses_configured_sheet_name(
	df_sample: pd.DataFrame,
	tmp_path: Path,
	mocker: MockerFixture,
) -> None:
	"""The configured sheet name reaches the I/O boundary.

	Mocks pandas' ``to_excel`` at the boundary so the test asserts behaviour
	without writing a real file.

	Parameters
	----------
	df_sample : pd.DataFrame
		Sample data to render.
	tmp_path : pathlib.Path
		Pytest-provided temporary directory.
	mocker : MockerFixture
		pytest-mock fixture for patching.

	Returns
	-------
	None
	"""
	mock_to_excel = mocker.patch.object(pd.DataFrame, "to_excel")
	path_out = tmp_path / "report.xlsx"
	RenderToExcel(path_out, str_sheet_name="custom").render(df_sample)
	mock_to_excel.assert_called_once()
	_, dict_kwargs = mock_to_excel.call_args
	assert dict_kwargs["sheet_name"] == "custom"
