"""JSON-file implementation of the database handler for local storage."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Optional

from .base import DatabaseHandler, Record, ensure_id


class JSONDatabaseHandler(DatabaseHandler):
    """Simple JSON-file storage for development and demos.

    Parameters
    ----------
    file_path : str or Path
        Location of the JSON file.
    id_field : str, optional
        Identifier field name, by default ``"id"``.
    """

    def __init__(self, file_path: str | Path, id_field: str = "id"):
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self.id_field = id_field
        if not self.file_path.exists():
            self.file_path.write_text("[]", encoding="utf-8")

    def create(self, record: Record) -> str:
        """Persist a record to the JSON store.

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
        """Fetch a record by its identifier.

        Parameters
        ----------
        record_id : str
            Identifier to look up.

        Returns
        -------
        Record or None
            Stored record when present, otherwise ``None``.
        """

        for row in self._read_all():
            if str(row.get(self.id_field)) == str(record_id):
                return row
        return None

    def update(self, record_id: str, updates: Record) -> Optional[Record]:
        """Update an existing record.

        Parameters
        ----------
        record_id : str
            Identifier of the record to update.
        updates : Record
            Partial payload containing fields to merge.

        Returns
        -------
        Record or None
            Updated record when found, otherwise ``None``.
        """

        rows: list[Record] = []
        updated: Optional[Record] = None
        for row in self._read_all():
            if str(row.get(self.id_field)) == str(record_id):
                row = {**row, **updates, self.id_field: record_id}
                updated = row
            rows.append(row)
        if updated is not None:
            self._write_all(rows)
        return updated

    def delete(self, record_id: str) -> bool:
        """Delete a record from the JSON file.

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

    def backup(self, target_path: str | Path) -> Path:
        """Create a file copy as a backup artifact."""

        target = Path(target_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(self.file_path, target)
        return target

    def _read_all(self) -> list[Record]:
        """Load all records from disk.

        Returns
        -------
        list of Record
            Records contained in the JSON file.
        """

        if not self.file_path.exists():
            return []
        content = self.file_path.read_text(encoding="utf-8")
        if not content.strip():
            return []
        return list(json.loads(content))

    def _write_all(self, rows: list[Record]) -> None:
        """Write all records to disk, replacing existing content.

        Parameters
        ----------
        rows : list of Record
            Records to persist.
        """

        self.file_path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
