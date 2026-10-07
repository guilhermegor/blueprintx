"""Unit tests for the pure row operations the CSV and JSON handlers share (blueprintx#650)."""

from __future__ import annotations

import pytest

from chassis.db_wschema.infrastructure._row_ops import _apply_update, _find_row, _row_has_id


LIST_ROWS = [{"id": "1", "v": "a"}, {"id": "2", "v": "b"}, {"id": "2", "v": "c"}]


@pytest.mark.parametrize(
    ("value", "str_expected"), [("1", True), (1, True), ("9", False), (None, False)]
)
def test_row_has_id_compares_as_strings(value: object, str_expected: bool) -> None:
    """The CSV backend returns every value as text, so ``1`` and ``"1"`` are the same id."""
    assert _row_has_id({"id": value} if value is not None else {}, "id", "1") is str_expected


def test_find_row_returns_the_first_match() -> None:
    """A duplicated id resolves to the first row, as the old loop did."""
    assert _find_row(LIST_ROWS, "id", "2") == {"id": "2", "v": "b"}


def test_find_row_returns_none_for_an_unknown_id() -> None:
    """No row carries the id."""
    assert _find_row(LIST_ROWS, "id", "9") is None


def test_apply_update_rewrites_every_matching_row() -> None:
    """Both rows with id ``2`` are merged, and the id is pinned."""
    list_out, _ = _apply_update(LIST_ROWS, "id", "2", {"v": "z", "id": "HACK"})

    assert list_out == [
        {"id": "1", "v": "a"},
        {"id": "2", "v": "z"},
        {"id": "2", "v": "z"},
    ]


def test_apply_update_reports_the_last_updated_row() -> None:
    """The returned record is the last match, as the old loop's ``dict_updated`` was."""
    _, dict_hit = _apply_update(LIST_ROWS, "id", "2", {"v": "z"})

    assert dict_hit == {"id": "2", "v": "z"}


def test_apply_update_reports_nothing_for_an_unknown_id() -> None:
    """``None`` tells the caller there is nothing to write back."""
    _, dict_hit = _apply_update(LIST_ROWS, "id", "9", {"v": "z"})

    assert dict_hit is None


def test_apply_update_leaves_its_input_unchanged() -> None:
    """The stored rows are not mutated in place."""
    list_before = [dict(row) for row in LIST_ROWS]
    _apply_update(LIST_ROWS, "id", "1", {"v": "z"})

    assert list_before == LIST_ROWS
