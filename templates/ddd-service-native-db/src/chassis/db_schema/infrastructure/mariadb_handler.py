"""MariaDB implementation of the database handler using mysql-connector-python."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
from typing import Any
from urllib.parse import urlparse


try:
	import mysql.connector as mysql_connector
except ImportError:  # pragma: no cover - optional dependency
	mysql_connector = None  # type: ignore[assignment]

from chassis.db.domain.ports import DatabaseHandler, Record
from chassis.db.infrastructure.helpers import DsnParts, ensure_id


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

	def __init__(self, dsn: str, table: str = "records", id_field: str = "id") -> None:
		if mysql_connector is None:
			raise ImportError(
				"mysql-connector-python is required for MariaDBDatabaseHandler; "
				"install it to use this backend."
			)
		self.dsn = dsn
		self.table = table
		self.id_field = id_field
		self.connection_kwargs: DsnParts = self._parse_dsn(dsn)
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
		json_payload = json.dumps(record)
		with self._connect() as cls_conn:
			cls_cur = cls_conn.cursor()
			cls_cur.execute(
				f"INSERT INTO {self.table} ({self.id_field}, data) VALUES (%s, %s) "  # noqa: S608
				f"ON DUPLICATE KEY UPDATE data = VALUES(data)",
				(record[self.id_field], json_payload),
			)
			cls_conn.commit()
		return str(record[self.id_field])

	def read(self, record_id: str) -> Record | None:
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
		with self._connect() as cls_conn:
			cls_cur = cls_conn.cursor()
			cls_cur.execute(
				f"SELECT data FROM {self.table} WHERE {self.id_field} = %s",  # noqa: S608
				(record_id,),
			)
			tuple_row = cls_cur.fetchone()
		if not tuple_row:
			return None
		return json.loads(tuple_row[0])

	def update(self, record_id: str, updates: Record) -> Record | None:
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
		dict_existing = self.read(record_id)
		if dict_existing is None:
			return None
		dict_updated = {**dict_existing, **updates, self.id_field: record_id}
		self.create(dict_updated)
		return dict_updated

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
		with self._connect() as cls_conn:
			cls_cur = cls_conn.cursor()
			cls_cur.execute(
				f"DELETE FROM {self.table} WHERE {self.id_field} = %s",  # noqa: S608
				(record_id,),
			)
			bool_deleted = cls_cur.rowcount > 0
			cls_conn.commit()
		return bool_deleted

	def backup(self, target_path: str | Path) -> Path:  # complexity-ok: dump + fallback tool
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
		path_target = Path(target_path)
		path_target.parent.mkdir(parents=True, exist_ok=True)

		dict_env = os.environ.copy()
		if self.password:
			dict_env["MARIADB_PWD"] = self.password
			dict_env["MYSQL_PWD"] = self.password

		list_dump_cmd = [
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
			with path_target.open("w", encoding="utf-8") as handle:
				subprocess.run(list_dump_cmd, stdout=handle, check=True, env=dict_env)  # noqa: S603
		except FileNotFoundError:
			list_fallback = list_dump_cmd[:]
			list_fallback[0] = "mysqldump"
			try:
				with path_target.open("w", encoding="utf-8") as handle:
					subprocess.run(list_fallback, stdout=handle, check=True, env=dict_env)  # noqa: S603
			except FileNotFoundError as err:
				raise RuntimeError(
					"mariadb-dump/mysqldump is required for MariaDB backups "
					"but was not found in PATH"
				) from err
			except subprocess.CalledProcessError as err:
				raise RuntimeError(f"mysqldump failed with exit code {err.returncode}") from err
		except subprocess.CalledProcessError as err:
			raise RuntimeError(f"mariadb-dump failed with exit code {err.returncode}") from err

		return path_target

	def close(self) -> None:
		"""Release resources (no-op; connections are per-call)."""

	def _connect(self) -> Any:
		"""Create a mysql-connector connection using the parsed DSN."""
		return mysql_connector.connect(**self.connection_kwargs)

	def _ensure_table(self) -> None:
		"""Create the backing table when it does not exist."""
		with self._connect() as cls_conn:
			cls_cur = cls_conn.cursor()
			cls_cur.execute(
				f"""
                CREATE TABLE IF NOT EXISTS {self.table} (
                    {self.id_field} VARCHAR(255) PRIMARY KEY,
                    data JSON NOT NULL
                )
                """
			)
			cls_conn.commit()

	def _parse_dsn(self, dsn: str) -> DsnParts:
		"""Parse a MariaDB DSN into keyword arguments for mysql-connector."""
		cls_parsed = urlparse(dsn)
		return {
			"user": cls_parsed.username or os.getenv("DB_USER"),
			"password": cls_parsed.password or os.getenv("DB_PASSWORD"),
			"host": cls_parsed.hostname or os.getenv("DB_HOST", "localhost"),
			"port": cls_parsed.port or int(os.getenv("DB_PORT", "3306")),
			"database": cls_parsed.path.lstrip("/") or os.getenv("DB_NAME"),
		}
