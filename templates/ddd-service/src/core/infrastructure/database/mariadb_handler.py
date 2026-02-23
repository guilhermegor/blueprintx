"""MariaDB implementation of the database handler using mysql-connector-python."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

try:
    import mysql.connector as mysql_connector  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    mysql_connector = None

from .base import DatabaseHandler, ensure_id
from .dto import Record


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
        self.host = self.connection_kwargs.get("host") or "localhost"
        self.port = int(self.connection_kwargs.get("port") or 3306)
        self.user = self.connection_kwargs.get("user") or "root"
        self.password = self.connection_kwargs.get("password") or ""
        self.dbname = self.connection_kwargs.get("database") or "app"
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

    def backup(self, target_path: str | Path) -> Path:
        """Create a MariaDB backup using mariadb-dump (falls back to mysqldump).

        Parameters
        ----------
        target_path : str or Path
            Destination path for the backup artifact.

        Returns
        -------
        Path
            Path to the created backup file.
        """

        target = Path(target_path)
        target.parent.mkdir(parents=True, exist_ok=True)

        env = os.environ.copy()
        if self.password:
            env["MARIADB_PWD"] = self.password
            env["MYSQL_PWD"] = self.password

        dump_cmd = [
            "mariadb-dump",
            "-h",
            self.host,
            "-P",
            str(self.port),
            "-u",
            self.user,
            self.dbname,
        ]

        try:
            with target.open("w", encoding="utf-8") as handle:
                subprocess.run(dump_cmd, stdout=handle, check=True, env=env)  # noqa: S603
        except FileNotFoundError:
            fallback = dump_cmd[:]
            fallback[0] = "mysqldump"
            try:
                with target.open("w", encoding="utf-8") as handle:
                    subprocess.run(fallback, stdout=handle, check=True, env=env)  # noqa: S603
            except FileNotFoundError as err:
                raise RuntimeError("mariadb-dump/mysqldump is required for MariaDB backups but was not found in PATH") from err
            except subprocess.CalledProcessError as err:
                raise RuntimeError(f"mysqldump failed with exit code {err.returncode}") from err
        except subprocess.CalledProcessError as err:
            raise RuntimeError(f"mariadb-dump failed with exit code {err.returncode}") from err

        return target

    def close(self) -> None:
        """Release resources (no-op; connections are per-call)."""

        return None

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
            "user": parsed.username or os.getenv("MARIADB_USER") or os.getenv("MYSQL_USER"),
            "password": parsed.password or os.getenv("MARIADB_PASSWORD") or os.getenv("MYSQL_PASSWORD"),
            "host": parsed.hostname or os.getenv("MARIADB_HOST", os.getenv("MYSQL_HOST", "localhost")),
            "port": parsed.port or int(os.getenv("MARIADB_PORT", os.getenv("MYSQL_PORT", "3306"))),
            "database": parsed.path.lstrip("/") or os.getenv("MARIADB_DB") or os.getenv("MYSQL_DB"),
        }
