"""Unit tests for the XML reader seam (utils/xml_reader.py)."""

from pathlib import Path

import pytest

from src.utils.xml_reader import (
	find_xml_row_problems,
	is_attribute_path,
	read_xml,
	text_path_columns,
)

# ⚠️ Bare import, NOT `src.utils.tabular_reader`: xml_reader.py itself imports FileContract /
# ContractError bare ("from utils.tabular_reader import ..."), because that is how the app
# imports it at runtime (there is no "src." prefix outside pytest's dual pythonpath). Pulling
# them from `src.utils.tabular_reader` here would load a SECOND, distinct module instance —
# a different FileContract class object — and the runtime type-checker would then reject a
# contract built from one instance when read_xml expects the other.
from utils.tabular_reader import ContractError, FileContract, ProblemReport


def _fixture_xml() -> str:
	"""Return a small ISO-20022-shaped fixture: two `Tx` rows, one `New` and one `Cxl`.

	Returns
	-------
	str
		The XML document text.
	"""
	return (
		"<Document>"
		"<FinInstrmRptgTxRpt>"
		"<Hdr><RptId>R1</RptId></Hdr>"
		"<Tx><New><FinInstrm><Id>ISIN123</Id></FinInstrm>"
		'<Pric><Pri><MntryVal Ccy="BRL">100.50</MntryVal></Pri></Pric>'
		"</New></Tx>"
		"<Tx><Cxl><FinInstrm><Id>ISIN456</Id></FinInstrm></Cxl></Tx>"
		"</FinInstrmRptgTxRpt>"
		"</Document>"
	)


def _empty_contract() -> FileContract:
	"""Return a contract that requires nothing, for tests exercising extraction only.

	Returns
	-------
	FileContract
		A permissive contract.
	"""
	return FileContract("tx", "tx", (), ())


def test_read_xml_extracts_one_row_per_anchor_using_ordered_alternative_paths(
	tmp_path: Path,
) -> None:
	"""Both record shapes (New/Cxl) yield a row via the two alternative Id paths."""
	path_xml = tmp_path / "fixture.xml"
	path_xml.write_text(_fixture_xml())
	df_result = read_xml(
		path_xml,
		"Tx",
		{"isin": ("New/FinInstrm/Id", "Cxl/FinInstrm/Id")},
		{"isin": "str"},
		_empty_contract(),
	)
	assert list(df_result["isin"]) == ["ISIN123", "ISIN456"]


def test_read_xml_wildcard_segment_matches_either_subblock_name(tmp_path: Path) -> None:
	"""A single-level `*` matches "New" and "Cxl" alike without listing either name."""
	path_xml = tmp_path / "fixture.xml"
	path_xml.write_text(_fixture_xml())
	df_result = read_xml(
		path_xml, "Tx", {"isin": ("*/FinInstrm/Id",)}, {"isin": "str"}, _empty_contract()
	)
	assert list(df_result["isin"]) == ["ISIN123", "ISIN456"]


def test_read_xml_wildcard_backtracks_past_a_non_completing_first_child(
	tmp_path: Path,
) -> None:
	"""A `*` tries every matching child, not just the first.

	A leading Meta block that has no FinInstrm must not hide the New block that comes after it.
	"""
	path_xml = tmp_path / "backtrack.xml"
	path_xml.write_text(
		"<Document><Tx>"
		"<Meta><Note>irrelevant</Note></Meta>"
		"<New><FinInstrm><Id>ISIN999</Id></FinInstrm></New>"
		"</Tx></Document>"
	)
	df_result = read_xml(
		path_xml, "Tx", {"isin": ("*/FinInstrm/Id",)}, {"isin": "str"}, _empty_contract()
	)
	assert list(df_result["isin"]) == ["ISIN999"]


def test_read_xml_row_filter_keeps_only_records_carrying_the_given_block(
	tmp_path: Path,
) -> None:
	"""str_row_filter="New" drops the Cxl-only Tx without re-anchoring the row tag."""
	path_xml = tmp_path / "fixture.xml"
	path_xml.write_text(_fixture_xml())
	df_result = read_xml(
		path_xml,
		"Tx",
		{"isin": ("New/FinInstrm/Id", "Cxl/FinInstrm/Id")},
		{"isin": "str"},
		_empty_contract(),
		str_row_filter="New",
	)
	assert list(df_result["isin"]) == ["ISIN123"]


def test_read_xml_attribute_path_matches_a_namespace_prefixed_attribute(
	tmp_path: Path,
) -> None:
	"""An `@name` path matches by LOCAL NAME, so a namespace-prefixed attribute still resolves.

	`Element.get("Ccy")` requires the exact stored key, which for a prefixed attribute is
	Clark notation (``{uri}Ccy``) — a naive `.get()` would silently miss it, dropping the
	currency exactly as a text-only path would.
	"""
	path_xml = tmp_path / "namespaced_attr.xml"
	path_xml.write_text(
		'<Document xmlns:xsi="urn:example:xsi"><Tx>'
		'<MntryVal xsi:Ccy="BRL">100.50</MntryVal>'
		"</Tx></Document>"
	)
	df_result = read_xml(
		path_xml, "Tx", {"ccy": ("MntryVal/@Ccy",)}, {"ccy": "str"}, _empty_contract()
	)
	assert list(df_result["ccy"]) == ["BRL"]


def test_read_xml_attribute_path_captures_the_currency_a_text_path_cannot(
	tmp_path: Path,
) -> None:
	"""Only an `@Ccy` path reaches the currency; no text path can see an attribute's value."""
	path_xml = tmp_path / "fixture.xml"
	path_xml.write_text(_fixture_xml())
	df_without_attr = read_xml(
		path_xml,
		"Tx",
		{"amount": ("New/Pric/Pri/MntryVal",)},
		{"amount": "str"},
		_empty_contract(),
		str_row_filter="New",
	)
	assert "ccy" not in df_without_attr.columns

	df_with_attr = read_xml(
		path_xml,
		"Tx",
		{"amount": ("New/Pric/Pri/MntryVal",), "ccy": ("New/Pric/Pri/MntryVal/@Ccy",)},
		{"amount": "str", "ccy": "str"},
		_empty_contract(),
		str_row_filter="New",
	)
	assert df_with_attr.loc[0, "ccy"] == "BRL"


def test_read_xml_absolute_path_broadcasts_one_scalar_to_every_row(tmp_path: Path) -> None:
	"""A leading-`/` path reads once from the document root and repeats on every row."""
	path_xml = tmp_path / "fixture.xml"
	path_xml.write_text(_fixture_xml())
	df_result = read_xml(
		path_xml,
		"Tx",
		{
			"isin": ("New/FinInstrm/Id", "Cxl/FinInstrm/Id"),
			"report_id": ("/FinInstrmRptgTxRpt/Hdr/RptId",),
		},
		{"isin": "str", "report_id": "str"},
		_empty_contract(),
	)
	assert list(df_result["report_id"]) == ["R1", "R1"]


def test_read_xml_matches_local_name_ignoring_namespace(tmp_path: Path) -> None:
	"""A namespaced document still resolves paths, matched by local name."""
	path_xml = tmp_path / "namespaced.xml"
	path_xml.write_text(
		'<Doc xmlns="urn:example:v1"><Row><Id>1</Id></Row><Row><Id>2</Id></Row></Doc>'
	)
	df_result = read_xml(path_xml, "Row", {"id": ("Id",)}, {"id": "str"}, _empty_contract())
	assert list(df_result["id"]) == ["1", "2"]


def test_read_xml_raises_contracterror_on_missing_required_column(tmp_path: Path) -> None:
	"""The contract is enforced exactly like read_table's: mandatory, checked before typing."""
	path_xml = tmp_path / "fixture.xml"
	path_xml.write_text(_fixture_xml())
	cls_contract = FileContract("tx", "tx", ("missing_col",), ())
	with pytest.raises(ContractError):
		read_xml(path_xml, "Tx", {"isin": ("New/FinInstrm/Id",)}, {"isin": "str"}, cls_contract)


def test_read_xml_raises_filenotfound_for_a_missing_file(tmp_path: Path) -> None:
	"""A missing file fails fast, like every other reader in this seam family."""
	with pytest.raises(FileNotFoundError):
		read_xml(tmp_path / "nope.xml", "Tx", {}, {}, _empty_contract())


def test_find_xml_row_problems_reports_a_missing_file_as_fatal(tmp_path: Path) -> None:
	"""A missing file is a FATAL finding, not a FileNotFoundError (the "never raises" half)."""
	cls_report = find_xml_row_problems(tmp_path / "nope.xml", "Tx", _empty_contract())
	assert "not found" in " ".join(cls_report.list_fatal)


def test_find_xml_row_problems_is_empty_when_rows_are_found(tmp_path: Path) -> None:
	"""A document carrying the expected row tag reports no problems."""
	path_xml = tmp_path / "fixture.xml"
	path_xml.write_text(_fixture_xml())
	cls_report = find_xml_row_problems(path_xml, "Tx", _empty_contract())
	assert cls_report == ProblemReport(list_fatal=[], list_warnings=[])


def test_find_xml_row_problems_reports_when_no_row_anchor_is_found(tmp_path: Path) -> None:
	"""A document with none of the expected row tag reports a FATAL problem, never raises."""
	path_xml = tmp_path / "empty.xml"
	path_xml.write_text("<Document></Document>")
	cls_report = find_xml_row_problems(path_xml, "Tx", _empty_contract())
	assert cls_report.list_fatal != []
	assert cls_report.list_warnings == []


def test_is_attribute_path_detects_a_trailing_attribute_segment() -> None:
	"""A path ending in `@name` is an attribute path; a plain trailing tag is not."""
	assert is_attribute_path("New/Pric/Pri/MntryVal/@Ccy") is True


def test_is_attribute_path_rejects_a_plain_text_path() -> None:
	"""A path with no `@`-segment is a text path."""
	assert is_attribute_path("New/Pric/Pri/MntryVal") is False


def test_text_path_columns_excludes_attribute_sourced_columns() -> None:
	"""An attribute column is excluded from the text-path (layout) column set."""
	dict_paths = {
		"amount": ("New/Pric/Pri/MntryVal",),
		"ccy": ("New/Pric/Pri/MntryVal/@Ccy",),
	}
	assert text_path_columns(dict_paths) == ("amount",)
