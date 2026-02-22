"""PostgreSQL implementation of the database handler using psycopg."""

from __future__ import annotations

import json
from typing import Optional

try:
    import psycopg
except ImportError:  # pragma: no cover - optional dependency
    psycopg = None

from .base import DatabaseHandler, Record, ensure_id


class PostgresDatabaseHandler(DatabaseHandler):
    """PostgreSQL handler using psycopg (install separately).

    Parameters
    ----------
    dsn : str
        Connection string for psycopg.
    table : str, optional
        Table name used for storage, by default ``"records"``.
    id_field : str, optional
        Identifier field name, by default ``"id"``.

    Raises
    ------
    ImportError
        If ``psycopg`` is not installed when instantiating the handler.
    """

    def __init__(self, dsn: str, table: str = "records", id_field: str = "id"):
        if psycopg is None:
            raise ImportError("psycopg is required for PostgresDatabaseHandler; install psycopg[binary].")
        self.dsn = dsn
        self.table = table
        self.id_field = id_field
        self._ensure_table()

    def create(self, record: Record) -> str:
        """Insert or update a record using an upsert.

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
        payload = json.dumps(record)
        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"INSERT INTO {self.table} ({self.id_field}, data) VALUES (%s, %s) "
                f"ON CONFLICT ({self.id_field}) DO UPDATE SET data = EXCLUDED.data",
                (record[self.id_field], payload),
            )
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
            Stored record when present, otherwise ``None``.
        """

        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT data FROM {self.table} WHERE {self.id_field} = %s", (record_id,)
            )
            row = cur.fetchone()
        if not row:
            return None
        return json.loads(row[0])

    def update(self, record_id: str, updates: Record) -> Optional[Record]:
        """Update an existing record.

        Parameters
        ----------
        record_id : str
            Identifier of the record to update.
        updates : Record
            Fields to merge into the existing record.

        Returns
        -------
        Record or None
            Updated record when it exists, otherwise ``None``.
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
            ``True`` when a record was deleted, ``False`` otherwise.
        """

        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"DELETE FROM {self.table} WHERE {self.id_field} = %s", (record_id,)
            )
            return cur.rowcount > 0

    def _connect(self):
        """Create a psycopg connection using the configured DSN."""

        return psycopg.connect(self.dsn)

    def _ensure_table(self) -> None:
        """Create the backing table when it does not exist."""

        with self._connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.table} (
                    {self.id_field} TEXT PRIMARY KEY,
                    data JSONB NOT NULL
                )
                """
            )
            conn.commit()
