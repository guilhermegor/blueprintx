"""Unit tests for the tabular reading seam (contract + dtype enforcement)."""

from pathlib import Path

import pytest

from src.utils.tabular_reader import ContractError, FileContract, find_file_problems, read_table


def _write_csv(path_dir: Path) -> Path:
	"""Write a small ``;``-separated CSV and return its path.

	Parameters
	----------
	path_dir : pathlib.Path
		Directory in which to create the file.

	Returns
	-------
	pathlib.Path
		Path to the created CSV.
	"""
	path_csv = path_dir / "data.csv"
	path_csv.write_text("code;amount\nABC;10\nDEF;20\n", encoding="utf-8")
	return path_csv


def test_read_table_applies_contract_and_dtypes(tmp_path: Path) -> None:
	"""A valid file passes its contract and the declared dtypes are applied."""
	path_csv = _write_csv(tmp_path)
	cls_contract = FileContract("data", "data", ("code", "amount"), ())
	pd = pytest.importorskip("pandas")
	df_out = read_table(path_csv, "", {"code": "str", "amount": "int64"}, cls_contract)
	assert list(df_out.columns) == ["code", "amount"]
	assert pd.api.types.is_string_dtype(df_out["code"])  # code typed as string
	assert str(df_out["amount"].dtype) == "int64"
	assert df_out["code"].iloc[0] == "ABC"


def test_read_table_raises_on_missing_required_column(tmp_path: Path) -> None:
	"""A missing required column raises ContractError before typing."""
	path_csv = _write_csv(tmp_path)
	cls_contract = FileContract("data", "data", ("code", "missing_col"), ())
	with pytest.raises(ContractError, match="missing_col"):
		read_table(path_csv, "", {"code": "str"}, cls_contract)


def test_find_file_problems_reports_without_raising(tmp_path: Path) -> None:
	"""find_file_problems returns the problem list instead of raising."""
	path_csv = _write_csv(tmp_path)
	cls_contract = FileContract("data", "data", ("code", "absent"), ())
	list_problems = find_file_problems(cls_contract, path_csv, "")
	assert any("absent" in p for p in list_problems)


def test_empty_contract_constrains_nothing(tmp_path: Path) -> None:
	"""An empty contract still declares intent and passes any well-formed file."""
	path_csv = _write_csv(tmp_path)
	cls_contract = FileContract("data", "data", (), ())
	df_out = read_table(path_csv, "", {"code": "str", "amount": "int64"}, cls_contract)
	assert len(df_out) == 2
