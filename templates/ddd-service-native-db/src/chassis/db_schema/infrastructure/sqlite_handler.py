"""SQLite implementation of the database handler for local storage."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import sqlite3

from chassis.db.domain.ports import DatabaseHandler, Record
from chassis.db.infrastructure.helpers import ensure_id


class SQLiteDatabaseHandler(DatabaseHandler):
	"""SQLite-backed storage for local development and tests.

	Parameters
	----------
	db_path : str or Path
		Location of the SQLite database file.
	table : str, optional
		Table name used for storage, by default ``"records"``.
	id_field : str, optional
		Identifier field name, by default ``"id"``.
	"""

	def __init__(self, db_path: str | Path, table: str = "records", id_field: str = "id") -> None:
		self.db_path = Path(db_path)
		self.db_path.parent.mkdir(parents=True, exist_ok=True)
		self.table = table
		self.id_field = id_field
		self._ensure_table()

	def create(self, record: Record) -> str:
		"""Insert or replace a record.

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
			cls_conn.execute(
				f"INSERT OR REPLACE INTO {self.table} ({self.id_field}, data) VALUES (?, ?)",  # noqa: S608
				(record[self.id_field], json_payload),
			)
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
			cls_cursor = cls_conn.execute(
				f"SELECT data FROM {self.table} WHERE {self.id_field} = ?",  # noqa: S608
				(record_id,),
			)
			tuple_row = cls_cursor.fetchone()
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
		"""Delete a record.

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
			cls_cursor = cls_conn.execute(
				f"DELETE FROM {self.table} WHERE {self.id_field} = ?",  # noqa: S608
				(record_id,),
			)
			return cls_cursor.rowcount > 0

	def backup(self, target_path: str | Path) -> Path:
		"""Copy the SQLite database file to the destination path."""
		path_target = Path(target_path)
		path_target.parent.mkdir(parents=True, exist_ok=True)
		shutil.copy2(self.db_path, path_target)
		return path_target

	def close(self) -> None:
		"""No-op because connections are short-lived per operation."""
		return None

	def _connect(self) -> sqlite3.Connection:
		"""Create a new SQLite connection.

		Returns
		-------
		sqlite3.Connection
			Connection bound to the configured database file.
		"""
		return sqlite3.connect(self.db_path)

	def _ensure_table(self) -> None:
		"""Create the backing table when it does not exist."""
		with self._connect() as cls_conn:
			cls_conn.execute(
				f"""
                CREATE TABLE IF NOT EXISTS {self.table} (
                    {self.id_field} TEXT PRIMARY KEY,
                    data TEXT NOT NULL
                )
                """
			)
