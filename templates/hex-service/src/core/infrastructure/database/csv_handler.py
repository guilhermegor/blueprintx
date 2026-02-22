"""CSV-backed implementation of the database handler for small datasets."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable, Optional

from .base import DatabaseHandler, Record, ensure_id


class CSVDatabaseHandler(DatabaseHandler):
    """Lightweight CSV-backed storage for development and testing.

    Parameters
    ----------
    file_path : str or Path
        Location of the CSV file.
    id_field : str, optional
        Identifier column name, by default ``"id"``.
    """

    def __init__(self, file_path: str | Path, id_field: str = "id"):
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.id_field = id_field
        if not self.file_path.exists():
            self.file_path.write_text("", encoding="utf-8")

    def create(self, record: Record) -> str:
        """Insert a record into the CSV store.

        Parameters
        ----------
        record : Record
            Data to persist.

        Returns
        -------
        str
            Identifier assigned to the stored record.
        """

        record = ensure_id(record, self.id_field)
        rows = self._read_all()
        rows.append(record)
        self._write_all(rows)
        return str(record[self.id_field])

    def read(self, record_id: str) -> Optional[Record]:
        """Retrieve a record by identifier.

        Parameters
        ----------
        record_id : str
            Identifier to look up.

        Returns
        -------
        Record or None
            Matching record when found, otherwise ``None``.
        """

        for row in self._read_all():
            if str(row.get(self.id_field)) == str(record_id):
                return row
        return None

    def update(self, record_id: str, updates: Record) -> Optional[Record]:
        """Update a stored record.

        Parameters
        ----------
        record_id : str
            Identifier of the record to update.
        updates : Record
            Partial payload to merge.

        Returns
        -------
        Record or None
            Updated record when it exists, otherwise ``None``.
        """

        updated: Optional[Record] = None
        rows: list[Record] = []
        for row in self._read_all():
            if str(row.get(self.id_field)) == str(record_id):
                row = {**row, **updates, self.id_field: record_id}
                updated = row
            rows.append(row)
        if updated is not None:
            self._write_all(rows)
        return updated

    def delete(self, record_id: str) -> bool:
        """Remove a record from the CSV file.

        Parameters
        ----------
        record_id : str
            Identifier of the record to remove.

        Returns
        -------
        bool
            ``True`` when a record was deleted, ``False`` otherwise.
        """

        rows = self._read_all()
        remaining = [row for row in rows if str(row.get(self.id_field)) != str(record_id)]
        if len(remaining) == len(rows):
            return False
        self._write_all(remaining)
        return True

    def _read_all(self) -> list[Record]:
        """Load all records from disk.

        Returns
        -------
        list of Record
            All records currently stored.
        """

        if not self.file_path.exists() or self.file_path.stat().st_size == 0:
            return []
        with self.file_path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            return [dict(row) for row in reader]

    def _write_all(self, rows: Iterable[Record]) -> None:
        """Write all records to disk, replacing existing data.

        Parameters
        ----------
        rows : Iterable[Record]
            Records to persist.
        """

        rows = list(rows)
        if not rows:
            self.file_path.write_text("", encoding="utf-8")
            return
        fieldnames = sorted({key for row in rows for key in row.keys()})
        with self.file_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
