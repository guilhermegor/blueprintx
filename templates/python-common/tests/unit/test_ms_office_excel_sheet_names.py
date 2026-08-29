"""Unit tests for Excel worksheet-name validation (utils/ms_office/excel_sheet_names.py)."""

from src.utils.ms_office.excel_sheet_names import (
	find_sheet_name_problems,
	find_workbook_sheet_name_problems,
)


def test_find_sheet_name_problems_accepts_a_sound_name() -> None:
	"""A short, plain, ASCII name with no rule broken reports no problems."""
	assert find_sheet_name_problems("Dados Abril") == []


def test_find_sheet_name_problems_flags_blank_name() -> None:
	"""An empty name is rejected — a blank tab breaks every write."""
	assert find_sheet_name_problems("") != []


def test_find_sheet_name_problems_flags_too_long_name() -> None:
	"""A name over 31 characters is rejected (Excel's own limit)."""
	assert find_sheet_name_problems("a" * 32) != []


def test_find_sheet_name_problems_flags_forbidden_characters() -> None:
	"""A name carrying an Excel-forbidden character (e.g. ``:``) is rejected."""
	assert find_sheet_name_problems("Q1:Q2") != []


def test_find_sheet_name_problems_flags_surrounding_whitespace() -> None:
	"""A name with leading/trailing whitespace is rejected."""
	assert find_sheet_name_problems(" Dados") != []


def test_find_sheet_name_problems_flags_leading_apostrophe() -> None:
	"""A name starting with an apostrophe is rejected."""
	assert find_sheet_name_problems("'Dados") != []


def test_find_sheet_name_problems_flags_reserved_name() -> None:
	"""The reserved name "History" is rejected case-insensitively."""
	assert find_sheet_name_problems("HISTORY") != []


def test_find_sheet_name_problems_accepts_cell_reference_shaped_names() -> None:
	"""A name shaped like a cell reference is a VALID worksheet name in Excel.

	The "cannot look like a cell reference" rule is real, but it governs *defined names*
	(the Name Manager), not worksheet tabs — a sheet literally named "Q1" is valid and is
	referenced as ``Q1!A1`` (verified against Microsoft's own worksheet-rename docs).
	"""
	assert find_sheet_name_problems("Q1") == []
	assert find_sheet_name_problems("H2") == []


def test_find_sheet_name_problems_flags_invisible_characters() -> None:
	"""A name carrying a zero-width space is rejected, and the character is named."""
	list_problems = find_sheet_name_problems("Dados" + "\u200b" + "Abril")
	assert list_problems != []
	assert "ZERO WIDTH SPACE" in list_problems[0]


def test_find_workbook_sheet_name_problems_flags_case_insensitive_duplicates() -> None:
	"""Sheet names differing only by case still collide in Excel."""
	list_problems = find_workbook_sheet_name_problems(["DADOS", "Dados"])
	assert "collide" in " ".join(list_problems)


def test_find_workbook_sheet_name_problems_accepts_a_sound_workbook() -> None:
	"""A workbook whose names are all sound and distinct reports no problems."""
	assert find_workbook_sheet_name_problems(["Resumo", "Detalhe"]) == []
