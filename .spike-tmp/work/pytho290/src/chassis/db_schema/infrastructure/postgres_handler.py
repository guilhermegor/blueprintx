"""PostgreSQL implementation of the database handler using psycopg."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
from typing import Any
from urllib.parse import urlparse


try:
	import psycopg
except ImportError:  # pragma: no cover - optional dependency
	psycopg = None  # type: ignore[assignment]

from chassis.db.domain.ports import DatabaseHandler, Record
from chassis.db.infrastructure.helpers import DsnParts, ensure_id


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

	def __init__(self, dsn: str, table: str = "records", id_field: str = "id") -> None:
		if psycopg is None:
			raise ImportError(
				"psycopg is required for PostgresDatabaseHandler; install psycopg[binary]."
			)
		self.dsn = dsn
		self.table = table
		self.id_field = id_field
		dict_parsed = self._parse_dsn(dsn)
		self.host = dict_parsed.get("host") or "localhost"
		self.port = dict_parsed.get("port") or 5432
		# ⚠️ Chain the literal default as its own "or" term rather than passing it to
		# os.getenv. Inside an "or", mypy resolves getenv's generic default against the
		# LEFT operand's type, so a getenv call with a string default comes back as str or None
		# and every argv built from it becomes a list of str-or-None. Chaining also fixes
		# a real behavioural gap — an env var set to the EMPTY string now falls back too,
		# instead of silently connecting as "".
		self.user = dict_parsed.get("user") or os.getenv("DB_USER") or "user"
		self.password = dict_parsed.get("password") or os.getenv("DB_PASSWORD") or "password"
		self.dbname = dict_parsed.get("database") or os.getenv("DB_NAME") or "app"
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
		with self._connect() as cls_conn, cls_conn.cursor() as cls_cur:
			cls_cur.execute(
				f"INSERT INTO {self.table} ({self.id_field}, data) VALUES (%s, %s) "  # noqa: S608
				f"ON CONFLICT ({self.id_field}) DO UPDATE SET data = EXCLUDED.data",
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
		with self._connect() as cls_conn, cls_conn.cursor() as cls_cur:
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
		with self._connect() as cls_conn, cls_conn.cursor() as cls_cur:
			cls_cur.execute(
				f"DELETE FROM {self.table} WHERE {self.id_field} = %s",  # noqa: S608
				(record_id,),
			)
			return cls_cur.rowcount > 0

	def backup(self, target_path: str | Path) -> Path:  # complexity-ok: dump + error translation
		"""Create a PostgreSQL backup using pg_dump in custom format.

		Parameters
		----------
		target_path : str or Path
			Destination path for the backup file.

		Returns
		-------
		Path
			Path to the created backup file.
		"""
		path_target = Path(target_path)
		path_target.parent.mkdir(parents=True, exist_ok=True)

		dict_env = os.environ.copy()
		if self.password:
			dict_env["PGPASSWORD"] = self.password

		list_command = [
			"pg_dump",
			"-h",
			self.host,
			"-p",
			str(self.port),
			"-U",
			self.user,
			"-F",
			"c",  # custom format for pg_restore
			"-b",  # include large objects
			"-f",
			str(path_target),
			self.dbname,
		]

		try:
			subprocess.run(list_command, check=True, env=dict_env)  # noqa: S603
		except FileNotFoundError as err:
			raise RuntimeError(
				"pg_dump is required for PostgreSQL backups but was not found in PATH"
			) from err
		except subprocess.CalledProcessError as err:
			raise RuntimeError(f"pg_dump failed with exit code {err.returncode}") from err

		return path_target

	def close(self) -> None:
		"""No-op because connections are opened per operation."""
		return None

	def _connect(self) -> Any:
		"""Create a psycopg connection using the configured DSN."""
		return psycopg.connect(self.dsn)

	def _parse_dsn(self, dsn: str) -> DsnParts:
		"""Parse a PostgreSQL DSN into connection parts for pg_dump."""
		cls_parsed = urlparse(dsn)
		return {
			"user": cls_parsed.username,
			"password": cls_parsed.password,
			"host": cls_parsed.hostname,
			"port": cls_parsed.port,
			"database": (cls_parsed.path.lstrip("/") if cls_parsed.path else None),
		}

	def _ensure_table(self) -> None:
		"""Create the backing table when it does not exist."""
		with self._connect() as cls_conn, cls_conn.cursor() as cls_cur:
			cls_cur.execute(
				f"""
                CREATE TABLE IF NOT EXISTS {self.table} (
                    {self.id_field} TEXT PRIMARY KEY,
                    data JSONB NOT NULL
                )
                """
			)
			cls_conn.commit()
