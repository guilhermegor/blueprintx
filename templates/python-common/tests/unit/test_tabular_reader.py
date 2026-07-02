"""Unit tests for the tabular reading seam (contract + dtype enforcement)."""

import csv
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


def _write_malformed_quote_csv(path_dir: Path) -> Path:
	"""Write a ``;``-CSV whose middle row has an unclosed ``"`` in a free-text field.

	Mirrors real CVM open data: an upstream submitter leaves a stray double quote in a
	deliberation field that also contains ``;``. The default reader treats the ``"`` as a
	field wrapper and swallows the delimiter (and following rows); ``QUOTE_NONE`` does not.

	Parameters
	----------
	path_dir : pathlib.Path
		Directory in which to create the file.

	Returns
	-------
	pathlib.Path
		Path to the created CSV.
	"""
	# The stray quote opens a free-text MIDDLE column, so the delimiter after it is the real
	# separator before amount. Under default quoting the open quote swallows that separator plus
	# the trailing rows, whereas QUOTE_NONE keeps the row's three real fields intact.
	path_csv = path_dir / "malformed.csv"
	path_csv.write_text(
		'code;note;amount\nABC;ok;10\nDEF;"parecer aprovado;20\nGHI;fine;30\n',
		encoding="utf-8",
	)
	return path_csv


def test_read_table_quote_none_reads_malformed_regulatory_dump(tmp_path: Path) -> None:
	"""csv.QUOTE_NONE reads every row of a ``;``-dump whose free-text field has a stray quote.

	Were the ``quoting`` argument not threaded through to the reader, the default
	``QUOTE_MINIMAL`` would treat the stray ``"`` as a field wrapper and either drop rows or
	raise a tokenizing error — so this positive read passing is itself the proof it is passed
	through (default-quoting corruption is pandas-version dependent, hence not asserted here).
	"""
	path_csv = _write_malformed_quote_csv(tmp_path)
	cls_contract = FileContract("data", "data", (), ())
	dict_dtypes = {"code": "str", "amount": "str", "note": "str"}
	df_none = read_table(path_csv, "", dict_dtypes, cls_contract, int_csv_quoting=csv.QUOTE_NONE)
	assert len(df_none) == 3  # all rows survive; the stray quote is literal text
	assert df_none["note"].iloc[1] == '"parecer aprovado'
	assert df_none["amount"].tolist() == ["10", "20", "30"]
