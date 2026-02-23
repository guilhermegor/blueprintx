"""Microsoft SQL Server implementation of the database handler using pyodbc."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Optional

try:
    import pyodbc  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    pyodbc = None

from .base import DatabaseHandler, ensure_id
from .dto import Record


class MSSQLDatabaseHandler(DatabaseHandler):
    """SQL Server handler using pyodbc.

    Parameters
    ----------
    connection_string : str
        ODBC connection string for ``pyodbc.connect``.
    table : str, optional
        Table name used for storage, by default ``"records"``.
    id_field : str, optional
        Identifier field name, by default ``"id"``.

    Raises
    ------
    ImportError
        If ``pyodbc`` is not installed when instantiating the handler.
    """

    def __init__(self, connection_string: str, table: str = "records", id_field: str = "id"):
        if pyodbc is None:
            raise ImportError("pyodbc is required for MSSQLDatabaseHandler; install it to use this backend.")
        self.connection_string = connection_string
        self.table = table
        self.id_field = id_field
        self._ensure_table()

    def create(self, record: Record) -> str:
        """Insert or update a record.

        Parameters
        ----------
        record : Record
            Data to persist; an ``id`` is generated if missing.

        Returns
        -------
        str
            Identifier assigned to the stored record.
        """

        record = ensure_id(record, self.id_field)
        payload = json.dumps(record)
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                f"MERGE {self.table} AS t USING (SELECT ? AS {self.id_field}, ? AS data) AS s "
                f"ON t.{self.id_field} = s.{self.id_field} "
                f"WHEN MATCHED THEN UPDATE SET data = s.data "
                f"WHEN NOT MATCHED THEN INSERT ({self.id_field}, data) VALUES (s.{self.id_field}, s.data);",
                (record[self.id_field], payload),
            )
            conn.commit()
        return str(record[self.id_field])

    def read(self, record_id: str) -> Optional[Record]:
        """Fetch a record by identifier.

        Parameters
        ----------
        record_id : str
            Identifier to look up.

        Returns
        -------
        Record or None
            Stored record if found, else ``None``.
        """

        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(f"SELECT data FROM {self.table} WHERE {self.id_field} = ?", (record_id,))
            row = cur.fetchone()
        if not row:
            return None
        return json.loads(row[0])

    def update(self, record_id: str, updates: Record) -> Optional[Record]:
        """Merge updates into an existing record.

        Parameters
        ----------
        record_id : str
            Identifier of the record to update.
        updates : Record
            Partial payload containing fields to override.

        Returns
        -------
        Record or None
            Updated record when found, else ``None``.
        """

        existing = self.read(record_id)
        if existing is None:
            return None
        updated = {**existing, **updates, self.id_field: record_id}
        self.create(updated)
        return updated

    def delete(self, record_id: str) -> bool:
        """Delete a record by identifier.

        Parameters
        ----------
        record_id : str
            Identifier of the record to remove.

        Returns
        -------
        bool
            ``True`` when a row was deleted, otherwise ``False``.
        """

        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(f"DELETE FROM {self.table} WHERE {self.id_field} = ?", (record_id,))
            deleted = cur.rowcount > 0
            conn.commit()
        return deleted

    def backup(self, target_path: str | Path) -> Path:
        """Stream all records to a JSON file as a backup artifact.

        Parameters
        ----------
        target_path : str or Path
            Destination path for the JSON backup.

        Returns
        -------
        Path
            Path to the created backup file.
        """

        target = Path(target_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8") as handle:
            with self._connect() as conn:
                cur = conn.cursor()
                cur.execute(f"SELECT data FROM {self.table}")
                rows = (json.loads(row[0]) for row in cur)
                handle.write(json.dumps(list(rows), indent=2, ensure_ascii=False))
        return target

    def close(self) -> None:
        """Release resources (no-op, connections are per-call)."""

        return None

    def _connect(self):
        """Create a pyodbc connection using the configured connection string."""

        return pyodbc.connect(self.connection_string)

    def _ensure_table(self) -> None:
        """Create the backing table when it does not exist."""

        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                f"""
                IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='{self.table}' AND xtype='U')
                BEGIN
                    CREATE TABLE {self.table} (
                        {self.id_field} NVARCHAR(255) PRIMARY KEY,
                        data NVARCHAR(MAX) NOT NULL
                    );
                END
                """
            )
            conn.commit()
