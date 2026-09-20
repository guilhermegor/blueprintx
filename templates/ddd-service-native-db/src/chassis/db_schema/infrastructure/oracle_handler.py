"""Oracle implementation of the database handler using oracledb (cx_Oracle)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


try:
	import oracledb
except ImportError:  # pragma: no cover - optional dependency
	oracledb = None  # type: ignore[assignment]

from chassis.db.domain.ports import DatabaseHandler, Record
from chassis.db.infrastructure.helpers import ensure_id


def _read_lob(value: Any) -> str:
	"""Return the text of an Oracle CLOB, or the value itself when already a string.

	Parameters
	----------
	value : Any
		Column value returned by ``oracledb``; a LOB object or a ``str``.

	Returns
	-------
	str
		Textual payload of the column.
	"""
	return value.read() if hasattr(value, "read") else value


class OracleDatabaseHandler(DatabaseHandler):
	"""Oracle handler using oracledb/cx_Oracle.

	Parameters
	----------
	dsn : str
		Oracle DSN string (e.g., ``host:port/service`` or EZCONNECT).
	user : str, optional
		Database user; falls back to ``DB_USER``.
	password : str, optional
		Database password; falls back to ``DB_PASSWORD``.
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
		user: str | None = None,
		password: str | None = None,
		table: str = "records",
		id_field: str = "id",
	) -> None:
		if oracledb is None:
			raise ImportError(
				"oracledb (cx_Oracle) is required for OracleDatabaseHandler; "
				"install it to use this backend."
			)
		self.dsn = dsn
		self.user = user or os.getenv("DB_USER")
		self.password = password or os.getenv("DB_PASSWORD")
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
				f"MERGE INTO {self.table} t USING "  # noqa: S608
				f"(SELECT :1 AS {self.id_field}, :2 AS data FROM dual) s "
				f"ON (t.{self.id_field} = s.{self.id_field}) "
				f"WHEN MATCHED THEN UPDATE SET data = s.data "
				f"WHEN NOT MATCHED THEN INSERT ({self.id_field}, data) "
				f"VALUES (s.{self.id_field}, s.data)",
				[record[self.id_field], payload],
			)
			conn.commit()
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
			Stored record if found, else ``None``.
		"""
		with self._connect() as conn:
			cur = conn.cursor()
			cur.execute(f"SELECT data FROM {self.table} WHERE {self.id_field} = :id", [record_id])  # noqa: S608
			row = cur.fetchone()
		if not row:
			return None
		return json.loads(_read_lob(row[0]))

	def update(self, record_id: str, updates: Record) -> Record | None:
		"""Merge updates into an existing record atomically.

		The read and the write share one transaction and the row is held by
		``SELECT … FOR UPDATE``, so a concurrent update cannot be lost. See
		``templates/python-common/CLAUDE.md`` → "DatabaseHandler contract".

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
		with self._connect() as cls_conn:
			cls_cur = cls_conn.cursor()
			cls_cur.execute(
				f"SELECT data FROM {self.table} WHERE {self.id_field} = :id FOR UPDATE",  # noqa: S608
				[record_id],
			)
			tuple_row = cls_cur.fetchone()
			if tuple_row is None:
				return None
			dict_stored = json.loads(_read_lob(tuple_row[0]))
			dict_updated = {**dict_stored, **updates, self.id_field: record_id}
			cls_cur.execute(
				f"UPDATE {self.table} SET data = :data WHERE {self.id_field} = :id",  # noqa: S608
				[json.dumps(dict_updated), record_id],
			)
			cls_conn.commit()
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
			``True`` when a row was deleted, otherwise ``False``.
		"""
		with self._connect() as conn:
			cur = conn.cursor()
			cur.execute(f"DELETE FROM {self.table} WHERE {self.id_field} = :id", [record_id])  # noqa: S608
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
		with target.open("w", encoding="utf-8") as handle, self._connect() as conn:
			cur = conn.cursor()
			cur.execute(f"SELECT data FROM {self.table}")  # noqa: S608
			rows = []
			for row in cur:
				cell = row[0]
				rows.append(json.loads(_read_lob(cell)))
			handle.write(json.dumps(rows, indent=2, ensure_ascii=False))
		return target

	def close(self) -> None:
		"""Release resources (no-op, connections are per-call)."""

	def _connect(self) -> Any:
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
