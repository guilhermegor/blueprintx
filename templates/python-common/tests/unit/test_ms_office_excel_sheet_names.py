"""Unit tests for Excel worksheet-name validation (utils/ms_office/excel_sheet_names.py)."""

from src.utils.ms_office.excel_sheet_names import (
    find_sheet_name_problems,
    find_workbook_sheet_name_problems,
)

# ⚠️ Bare import, NOT `src.utils.tabular_reader`: excel_sheet_names.py itself imports
# ProblemReport bare ("from utils.tabular_reader import ProblemReport"), because that is how
# the app imports it at runtime. Pulling it from `src.utils.tabular_reader` here would load a
# SECOND, distinct module instance — a different ProblemReport class object — and the
# TypeChecker-guarded dataclass's own equality check would then reject an instance built from
# one against an instance built from the other, even with identical field values. See
# tests/CLAUDE.md ("The dual-import-root trap").
from utils.tabular_reader import ProblemReport


_EMPTY_REPORT = ProblemReport(list_fatal=[], list_warnings=[])


def _is_fatal_only(cls_report: ProblemReport) -> bool:
    """Return whether the report classifies its finding as FATAL and *only* fatal.

    Asserting ``list_fatal != []`` alone does not test the severity split this module exists
    for: a finding wrongly placed in BOTH lists would pass. The pair of checks is one
    behaviour — "classified fatal" — so it lives in one named predicate rather than in two
    assertions per test.
    """
    return cls_report.list_fatal != [] and cls_report.list_warnings == []


def test_find_sheet_name_problems_accepts_a_sound_name() -> None:
    """A short, plain, ASCII name with no rule broken reports no problems."""
    assert find_sheet_name_problems("Dados Abril") == _EMPTY_REPORT


def test_find_sheet_name_problems_flags_blank_name() -> None:
    """An empty name is rejected as FATAL — a blank tab breaks every write."""
    assert _is_fatal_only(find_sheet_name_problems(""))


def test_find_sheet_name_problems_flags_too_long_name() -> None:
    """A name over 31 characters is rejected as FATAL (Excel's own limit)."""
    assert find_sheet_name_problems("a" * 32).list_fatal != []


def test_find_sheet_name_problems_flags_forbidden_characters() -> None:
    """A name carrying an Excel-forbidden character (e.g. ``:``) is rejected as FATAL."""
    assert find_sheet_name_problems("Q1:Q2").list_fatal != []


def test_find_sheet_name_problems_flags_surrounding_whitespace() -> None:
    """A name with leading/trailing whitespace is rejected as FATAL.

    Every rule here guards the same write boundary — openpyxl/Excel silently corrupt the
    name regardless of which rule broke — so this is fatal too, not merely cosmetic.
    """
    assert find_sheet_name_problems(" Dados").list_fatal != []


def test_find_sheet_name_problems_flags_leading_apostrophe() -> None:
    """A name starting with an apostrophe is rejected as FATAL."""
    assert find_sheet_name_problems("'Dados").list_fatal != []


def test_find_sheet_name_problems_flags_reserved_name() -> None:
    """The reserved name "History" is rejected case-insensitively, as FATAL."""
    assert find_sheet_name_problems("HISTORY").list_fatal != []


def test_find_sheet_name_problems_accepts_cell_reference_shaped_names() -> None:
    """A name shaped like a cell reference is a VALID worksheet name in Excel.

    The "cannot look like a cell reference" rule is real, but it governs *defined names*
    (the Name Manager), not worksheet tabs — a sheet literally named "Q1" is valid and is
    referenced as ``Q1!A1`` (verified against Microsoft's own worksheet-rename docs).
    """
    assert find_sheet_name_problems("Q1") == _EMPTY_REPORT
    assert find_sheet_name_problems("H2") == _EMPTY_REPORT


def test_find_sheet_name_problems_flags_invisible_characters() -> None:
    """A name carrying a zero-width space is rejected as FATAL, and the character is named."""
    cls_report = find_sheet_name_problems("Dados" + "\u200b" + "Abril")
    assert "ZERO WIDTH SPACE" in " ".join(cls_report.list_fatal)


def test_find_workbook_sheet_name_problems_flags_case_insensitive_duplicates() -> None:
    """Sheet names differing only by case still collide in Excel, and the message says so."""
    cls_report = find_workbook_sheet_name_problems(["DADOS", "Dados"])
    assert "collide" in " ".join(cls_report.list_fatal)


def test_find_workbook_sheet_name_problems_classifies_duplicates_as_fatal_only() -> None:
    """The duplicate finding is FATAL and *only* fatal — a caller reading warnings sees none."""
    assert _is_fatal_only(find_workbook_sheet_name_problems(["DADOS", "Dados"]))


def test_find_workbook_sheet_name_problems_accepts_a_sound_workbook() -> None:
    """A workbook whose names are all sound and distinct reports no problems."""
    assert find_workbook_sheet_name_problems(["Resumo", "Detalhe"]) == _EMPTY_REPORT
