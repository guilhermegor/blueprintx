"""MariaDB implementation of the database handler using mysql-connector-python."""

from __future__ import annotations

import json
from typing import Optional
from urllib.parse import urlparse

try:
    import mysql.connector as mysql_connector  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    mysql_connector = None

from .base import DatabaseHandler, Record, ensure_id


class MariaDBDatabaseHandler(DatabaseHandler):
    """MariaDB handler using mysql-connector-python.

    Parameters
    ----------
    dsn : str
        Connection string for mysql-connector.
    table : str, optional
        Table name used for storage, by default ``"records"``.
    id_field : str, optional
        Identifier field name, by default ``"id"``.

    Raises
    ------
    ImportError
        If ``mysql-connector-python`` is not installed when instantiating the handler.
    """

    def __init__(self, dsn: str, table: str = "records", id_field: str = "id"):
        if mysql_connector is None:
            raise ImportError(
                "mysql-connector-python is required for MariaDBDatabaseHandler; install it to use this backend."
            )
        self.dsn = dsn
        self.table = table
        self.id_field = id_field
        self.connection_kwargs = self._parse_dsn(dsn)
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
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                f"INSERT INTO {self.table} ({self.id_field}, data) VALUES (%s, %s) "
                f"ON DUPLICATE KEY UPDATE data = VALUES(data)",
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
            Stored record when present, otherwise ``None``.
        """

        with self._connect() as conn:
            cur = conn.cursor()
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

        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                f"DELETE FROM {self.table} WHERE {self.id_field} = %s", (record_id,)
            )
            deleted = cur.rowcount > 0
            conn.commit()
        return deleted

    def _connect(self):
        """Create a mysql-connector connection using the parsed DSN."""

        return mysql_connector.connect(**self.connection_kwargs)  # type: ignore[arg-type]

    def _ensure_table(self) -> None:
        """Create the backing table when it does not exist."""

        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.table} (
                    {self.id_field} VARCHAR(255) PRIMARY KEY,
                    data JSON NOT NULL
                )
                """
            )
            conn.commit()

    def _parse_dsn(self, dsn: str) -> dict[str, object]:
        """Parse a MariaDB DSN into keyword arguments for mysql-connector."""

        parsed = urlparse(dsn)
        return {
            "user": parsed.username or "",
            "password": parsed.password or "",
            "host": parsed.hostname or "localhost",
            "port": parsed.port or 3306,
            "database": parsed.path.lstrip("/") or None,
        }
