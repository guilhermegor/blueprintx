"""Unit tests for the tabular reading seam (contract + dtype enforcement)."""

import csv
from pathlib import Path

import pytest

from src.utils.tabular_reader import (
	ContractError,
	FileContract,
	ProblemReport,
	find_file_problems,
	read_table,
)


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


def test_read_table_reads_as_text_preserving_zero_padding_and_decimals(tmp_path: Path) -> None:
	"""A zero-padded code and a money decimal survive the read intact (text-first, no inference).

	The regression this guards: reading with pandas' inference (``dtype=None``) parses ``007``
	to the int ``7`` and ``1000.50`` to the float ``1000.5`` *before* typing, and a later
	``astype`` cannot recover the dropped leading/trailing zeros. Reading as raw text keeps the
	exact source characters, so the declared dtype coerces from ``"007"`` / ``"1000.50"``.
	"""
	path_csv = tmp_path / "padded.csv"
	path_csv.write_text("code;amount\n007;1000.50\n042;0.10\n", encoding="utf-8")
	cls_contract = FileContract("data", "data", ("code", "amount"), ())
	df_out = read_table(path_csv, "", {"code": "str", "amount": "str"}, cls_contract)
	assert df_out["code"].tolist() == ["007", "042"]  # leading zeros survive
	assert df_out["amount"].tolist() == ["1000.50", "0.10"]  # trailing zeros survive


def test_read_table_raises_on_missing_required_column(tmp_path: Path) -> None:
	"""A missing required column raises ContractError before typing."""
	path_csv = _write_csv(tmp_path)
	cls_contract = FileContract("data", "data", ("code", "missing_col"), ())
	with pytest.raises(ContractError, match="missing_col"):
		read_table(path_csv, "", {"code": "str"}, cls_contract)


def test_find_file_problems_reports_without_raising(tmp_path: Path) -> None:
	"""find_file_problems returns a ProblemReport instead of raising."""
	path_csv = _write_csv(tmp_path)
	cls_contract = FileContract("data", "data", ("code", "absent"), ())
	cls_report = find_file_problems(cls_contract, path_csv, "")
	assert any("absent" in p for p in cls_report.list_fatal)


def test_find_file_problems_missing_column_is_fatal_never_a_warning(tmp_path: Path) -> None:
	"""A missing required column lands in ``list_fatal``, never in ``list_warnings``.

	Should-fail witness for blueprintx#162: under the OLD flat-list shape, a caller wanting to
	"proceed with a note" on cosmetic problems had to string-match messages — e.g. skip
	anything mentioning "CNPJ" — and nothing stopped it from ALSO matching a missing-column
	message by accident, silently swallowing a fatal problem as a warning. Under the new
	shape that mistake is unrepresentable: a caller reading only ``list_warnings`` (its
	"proceed" branch) cannot see this finding at all, because it is never placed there.
	"""
	path_csv = _write_csv(tmp_path)
	cls_contract = FileContract("data", "data", ("code", "absent"), ())
	cls_report = find_file_problems(cls_contract, path_csv, "")
	assert any("absent" in p for p in cls_report.list_fatal)
	assert cls_report.list_warnings == []


def test_header_only_file_passes_its_cnpj_contract(tmp_path: Path) -> None:
	"""A source reporting "nothing today" by shipping its header alone is not a broken file.

	Negative control for the ``any()``-over-an-empty-series trap: ``any()`` of an empty series
	is ``False``, the same answer a column of garbage gives, so the pre-fix code reproved a
	well-formed header-only file as "holds no valid CNPJ" and killed the run.
	"""
	path_csv = tmp_path / "empty.csv"
	path_csv.write_text("cnpj;amount\n", encoding="utf-8")
	cls_contract = FileContract("data", "data", ("cnpj", "amount"), ("cnpj",))
	cls_report = find_file_problems(cls_contract, path_csv, "")
	assert cls_report == ProblemReport(list_fatal=[], list_warnings=[])


def test_populated_cnpj_column_with_no_valid_value_is_a_warning_not_fatal(
	tmp_path: Path,
) -> None:
	"""A populated-but-invalid CNPJ column is reported, but as a WARNING, never fatal.

	The other half of the control above: skipping an empty column is right, skipping a
	populated-but-invalid one would delete the check entirely — it must still be reported.
	It is content-quality, not structural (the column is present, the shape is sound), which
	is why it belongs in ``list_warnings`` rather than ``list_fatal`` — see the should-fail
	witness in ``test_find_file_problems_missing_column_is_fatal_never_a_warning``.
	"""
	path_csv = tmp_path / "garbage.csv"
	path_csv.write_text("cnpj;amount\nnot-a-cnpj;10\nalso-not;20\n", encoding="utf-8")
	cls_contract = FileContract("data", "data", ("cnpj", "amount"), ("cnpj",))
	cls_report = find_file_problems(cls_contract, path_csv, "")
	assert any("holds no valid CNPJ" in p for p in cls_report.list_warnings)
	assert cls_report.list_fatal == []


def test_missing_cnpj_value_is_not_stringified_to_nan(tmp_path: Path) -> None:
	"""A blank cell must not reach the validator as the literal string ``"nan"``.

	``.astype(str)`` is not NA-safe below pandas 3: it renders a missing value as ``"nan"``,
	which then fails validation for the wrong reason. ``safe_str`` yields ``""``. A valid
	sibling row keeps the column passing, proving the blank was skipped rather than counted.
	"""
	path_csv = tmp_path / "blank.csv"
	path_csv.write_text("cnpj;amount\n;10\n11.222.333/0001-81;20\n", encoding="utf-8")
	cls_contract = FileContract("data", "data", ("cnpj", "amount"), ("cnpj",))
	cls_report = find_file_problems(cls_contract, path_csv, "")
	assert cls_report == ProblemReport(list_fatal=[], list_warnings=[])


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


def test_read_table_json_preserves_zero_padding_and_decimal_scale(tmp_path: Path) -> None:
	"""The JSON branch honours the same "read as text" guarantee the CSV branch does.

	``read_table``'s docstring promises the file is *always* read as text, never with pandas'
	inference — but the JSON branch used ``pd.read_json``, which infers regardless. Measured:
	it returns ``1000.5`` for a document that literally contains the STRING ``"1000.50"``, and
	``7`` for ``"007"``. The scale is unrecoverable afterwards, so a money column ingested from
	an API silently lost its cents.
	"""
	path_json = tmp_path / "money.json"
	path_json.write_text(
		'[{"code": "007", "amount": "1000.50"}, {"code": "042", "amount": 0.10}]',
		encoding="utf-8",
	)
	cls_contract = FileContract("data", "data", ("code", "amount"), ())
	df_out = read_table(path_json, "", {"code": "str", "amount": "str"}, cls_contract)
	assert df_out["code"].tolist() == ["007", "042"]  # leading zeros survive
	# The second row arrives as a bare JSON number — the exact source token still survives.
	assert df_out["amount"].tolist() == ["1000.50", "0.10"]


def test_padded_column_name_is_stripped_at_the_read_boundary(tmp_path: Path) -> None:
	"""A header cell with a trailing space must not produce an unreachable column.

	The nasty part is that it does not look like a defect: the column PRINTS as ``amount``
	while only ``df["amount "]`` reaches it, so the contract reports a required column missing
	and every lookup raises KeyError on a name plainly visible in ``df.columns``. It is
	per-dataset, never per-format — a sibling table from the same publisher is usually clean.
	"""
	path_csv = tmp_path / "padded_header.csv"
	path_csv.write_text("code ;amount \nABC;10\n", encoding="utf-8")
	cls_contract = FileContract("data", "data", ("code", "amount"), ())
	df_out = read_table(path_csv, "", {"code": "str", "amount": "str"}, cls_contract)
	assert list(df_out.columns) == ["code", "amount"]


def test_positional_payload_drops_a_surplus_position_that_is_empty_everywhere(
	tmp_path: Path,
) -> None:
	"""A row wider than its header is tolerated only when the surplus is empty on every row."""
	path_json = tmp_path / "wide.json"
	path_json.write_text(
		'{"columns": ["code", "amount"], "rows": [["ABC", "10", null], ["DEF", "20", null]]}',
		encoding="utf-8",
	)
	cls_contract = FileContract("data", "data", ("code", "amount"), ())
	df_out = read_table(path_json, "", {"code": "str", "amount": "str"}, cls_contract)
	assert list(df_out.columns) == ["code", "amount"]
	assert df_out["amount"].tolist() == ["10", "20"]


def test_positional_payload_raises_when_the_surplus_holds_a_value(tmp_path: Path) -> None:
	"""A surplus position carrying data must raise, never be trimmed away.

	The payload is positional, so a surplus value cannot be named — and blind trimming is
	exactly how a source column stops arriving with nothing going red: a contract validates
	column PRESENCE, not payload WIDTH.
	"""
	path_json = tmp_path / "wide_valued.json"
	path_json.write_text(
		'{"columns": ["code", "amount"], "rows": [["ABC", "10", "surprise"]]}',
		encoding="utf-8",
	)
	cls_contract = FileContract("data", "data", ("code", "amount"), ())
	with pytest.raises(ContractError, match="surplus position"):
		read_table(path_json, "", {"code": "str", "amount": "str"}, cls_contract)


def test_positional_payload_raises_on_a_row_narrower_than_its_header(tmp_path: Path) -> None:
	"""A short row is a defect too — padding it would invent data."""
	path_json = tmp_path / "narrow.json"
	path_json.write_text('{"columns": ["code", "amount"], "rows": [["ABC"]]}', encoding="utf-8")
	cls_contract = FileContract("data", "data", ("code", "amount"), ())
	with pytest.raises(ContractError, match="narrower"):
		read_table(path_json, "", {"code": "str", "amount": "str"}, cls_contract)


def test_column_names_colliding_after_trimming_are_rejected(tmp_path: Path) -> None:
	"""Two names that differ only by surrounding spaces must not silently become one.

	Stripping is the fix for an unreachable padded column, but it can collide: a source
	shipping both ``code`` and ``code `` yields two columns named ``code``. The contract's
	required-column check still passes — the name IS present — while every later lookup
	returns a DataFrame instead of a Series and ``apply_dtypes`` types an ambiguous schema.
	"""
	path_csv = tmp_path / "collide.csv"
	path_csv.write_text("code;code ;amount\nABC;DEF;10\n", encoding="utf-8")
	cls_contract = FileContract("data", "data", ("code",), ())
	with pytest.raises(ContractError, match="collide after trimming"):
		read_table(path_csv, "", {"code": "str", "amount": "str"}, cls_contract)
