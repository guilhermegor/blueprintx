"""Pure row operations shared by the file-backed storage handlers (CSV and JSON)."""

from __future__ import annotations

from collections.abc import Iterable

from chassis.db.domain.ports import Record


def _row_has_id(dict_row: Record, str_id_field: str, record_id: str) -> bool:
    """Return whether a row carries the given identifier.

    Compared as strings on both sides, because the CSV backend reads every value back as text.

    Parameters
    ----------
    dict_row : Record
            Row to test.
    str_id_field : str
            Name of the identifier field.
    record_id : str
            Identifier to look for.

    Returns
    -------
    bool
            ``True`` when the row's identifier equals ``record_id``.
    """
    return str(dict_row.get(str_id_field)) == str(record_id)


def _find_row(list_rows: Iterable[Record], str_id_field: str, record_id: str) -> Record | None:
    """Return the first row carrying the identifier, or ``None``.

    Parameters
    ----------
    list_rows : Iterable[Record]
            Rows to search.
    str_id_field : str
            Name of the identifier field.
    record_id : str
            Identifier to look for.

    Returns
    -------
    Record or None
            First matching row, otherwise ``None``.
    """
    return next((row for row in list_rows if _row_has_id(row, str_id_field, record_id)), None)


def _apply_update(
    list_rows: list[Record], str_id_field: str, record_id: str, dict_updates: Record
) -> tuple[list[Record], Record | None]:
    """Merge ``dict_updates`` into every row carrying the identifier.

    Parameters
    ----------
    list_rows : list of Record
            Rows as currently stored; not modified.
    str_id_field : str
            Name of the identifier field.
    record_id : str
            Identifier of the rows to update.
    dict_updates : Record
            Partial payload to merge; the identifier is pinned to ``record_id``.

    Returns
    -------
    tuple of (list of Record, Record or None)
            The rows to write back, and the last row that was updated (``None`` when no row
            matched, which tells the caller there is nothing to write).
    """
    list_out = [
        {**dict_row, **dict_updates, str_id_field: record_id}
        if _row_has_id(dict_row, str_id_field, record_id)
        else dict_row
        for dict_row in list_rows
    ]
    list_hits = [
        dict_out
        for dict_out, dict_row in zip(list_out, list_rows, strict=True)
        if dict_out is not dict_row
    ]
    return list_out, next(reversed(list_hits), None)
