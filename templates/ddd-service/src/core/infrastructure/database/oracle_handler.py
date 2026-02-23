"""Oracle implementation of the database handler using oracledb (cx_Oracle)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

try:
    import oracledb  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    oracledb = None

from .base import DatabaseHandler, ensure_id
from .dto import Record


class OracleDatabaseHandler(DatabaseHandler):
    """Oracle handler using oracledb/cx_Oracle.

    Parameters
    ----------
    dsn : str
        Oracle DSN string (e.g., ``host:port/service`` or EZCONNECT).
    user : str, optional
        Database user; falls back to ``ORACLE_USER``/``ORA_USER``.
    password : str, optional
        Database password; falls back to ``ORACLE_PASSWORD``/``ORA_PASSWORD``.
    table : str, optional
        Table name used for storage, by default ``"records"``.
    id_field : str, optional
        Identifier field name, by default ``"id"``.

    Raises
    ------
    ImportError
        If ``oracledb``/``cx_Oracle`` is not installed when instantiating the handler.
    """

    def __init__(
        self,
        dsn: str,
        user: Optional[str] = None,
        password: Optional[str] = None,
        table: str = "records",
        id_field: str = "id",
    ):
        if oracledb is None:
            raise ImportError("oracledb (cx_Oracle) is required for OracleDatabaseHandler; install it to use this backend.")
        self.dsn = dsn
        self.user = user or os.getenv("ORACLE_USER") or os.getenv("ORA_USER")
        self.password = password or os.getenv("ORACLE_PASSWORD") or os.getenv("ORA_PASSWORD")
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
                f"MERGE INTO {self.table} t USING (SELECT :1 AS {self.id_field}, :2 AS data FROM dual) s "
                f"ON (t.{self.id_field} = s.{self.id_field}) "
                f"WHEN MATCHED THEN UPDATE SET data = s.data "
                f"WHEN NOT MATCHED THEN INSERT ({self.id_field}, data) VALUES (s.{self.id_field}, s.data)",
                [record[self.id_field], payload],
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
            cur.execute(f"SELECT data FROM {self.table} WHERE {self.id_field} = :id", [record_id])
            row = cur.fetchone()
        if not row:
            return None
        return json.loads(row[0].read() if hasattr(row[0], "read") else row[0])

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
            cur.execute(f"DELETE FROM {self.table} WHERE {self.id_field} = :id", [record_id])
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
                rows = []
                for row in cur:
                    cell = row[0]
                    rows.append(json.loads(cell.read() if hasattr(cell, "read") else cell))
                handle.write(json.dumps(rows, indent=2, ensure_ascii=False))
        return target

    def close(self) -> None:
        """Release resources (no-op, connections are per-call)."""

        return None

    def _connect(self):
        """Create an Oracle connection using the configured DSN."""

        return oracledb.connect(user=self.user, password=self.password, dsn=self.dsn)

    def _ensure_table(self) -> None:
        """Create the backing table when it does not exist."""

        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT COUNT(*) FROM user_tables WHERE table_name = :tbl",
                {"tbl": self.table.upper()},
            )
            exists = cur.fetchone()[0] > 0
            if not exists:
                cur.execute(
                    f"CREATE TABLE {self.table} (\n"
                    f"  {self.id_field} VARCHAR2(255) PRIMARY KEY,\n"
                    f"  data CLOB NOT NULL\n"
                    f")"
                )
                conn.commit()
