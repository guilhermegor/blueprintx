"""Concurrency regression tests for ``DatabaseHandler.update()`` (blueprintx#561).

Two callers updating DIFFERENT fields of one record must both survive. The defect these
tests pin did a read-modify-write across two connections, so the later writer overwrote the
earlier writer's field with the pre-state it had read — silently, with no error anywhere.

Two shapes, because only SQLite can be raced for real without a server:

1. **SQLite** — a genuine two-thread race. ``json.loads`` is swapped for a stalling version,
   which widens the read-to-write window in BOTH the broken and the fixed implementation;
   the fixed one survives because ``BEGIN IMMEDIATE`` makes the second writer queue.
2. **The five server-backed handlers** — a recording fake driver asserting the two properties
   a real race would test: the read and the write go through ONE connection, and the read
   carries that dialect's row lock. Reverting the fix fails both (``self.read()`` plus
   ``self.create()`` opens two connections and locks nothing).

The atomicity contract itself is on the ``DatabaseHandler`` ABC and in
``templates/python-common/CLAUDE.md`` → "DatabaseHandler contract".
"""

from __future__ import annotations

from functools import partial
import importlib
import json
from pathlib import Path
import threading
import time
from types import SimpleNamespace

import pytest

from chassis.db.domain.ports import DatabaseHandler, Record
from chassis.db_schema.infrastructure import sqlite_handler
from chassis.db_schema.infrastructure.sqlite_handler import SQLiteDatabaseHandler


FLOAT_STALL_SECONDS = 0.25
STR_RECORD_ID = "r1"

# Dialect -> the fragment its locked SELECT must carry. The values differ because the atomic
# construct genuinely differs per backend; the table in python-common/CLAUDE.md is the source.
DICT_LOCKED_SELECT = {
	"mariadb_handler.MariaDBDatabaseHandler": "FOR UPDATE",
	"mssql_handler.MSSQLDatabaseHandler": "UPDLOCK, ROWLOCK",
	"mysql_handler.MySQLDatabaseHandler": "FOR UPDATE",
	"oracle_handler.OracleDatabaseHandler": "FOR UPDATE",
	"postgres_handler.PostgresDatabaseHandler": "FOR UPDATE",
}


def _stalling_loads(str_payload: str) -> Record:
	"""Parse JSON after a stall, widening the window between the read and the write.

	Parameters
	----------
	str_payload : str
		Serialised record read out of the ``data`` column.

	Returns
	-------
	Record
		The parsed record.
	"""
	time.sleep(FLOAT_STALL_SECONDS)
	return json.loads(str_payload)


def _update_one_field(
	cls_handler: SQLiteDatabaseHandler,
	str_field: str,
	cls_barrier: threading.Barrier,
) -> None:
	"""Write one field of the shared record, released in step with the sibling thread.

	Parameters
	----------
	cls_handler : SQLiteDatabaseHandler
		Handler under test.
	str_field : str
		Name of the single field this writer owns.
	cls_barrier : threading.Barrier
		Barrier both writers wait on so their updates overlap.
	"""
	cls_barrier.wait()
	cls_handler.update(STR_RECORD_ID, {str_field: "written"})


class RecordingCursor:
	"""Cursor stand-in that records every statement and replays one stored row."""

	def __init__(self, list_sql: list[str], str_stored: str) -> None:
		"""Store the shared statement log and the row to replay.

		Parameters
		----------
		list_sql : list of str
			Log every executed statement is appended to.
		str_stored : str
			Serialised record the ``SELECT`` returns.
		"""
		self.list_sql = list_sql
		self.str_stored = str_stored

	def execute(self, str_sql: str, *args: object) -> None:
		"""Record a statement instead of running it.

		Parameters
		----------
		str_sql : str
			Statement text.
		*args : object
			Bound parameters, ignored.
		"""
		self.list_sql.append(str_sql)

	def fetchone(self) -> tuple[str]:
		"""Return the single stored row.

		Returns
		-------
		tuple of str
			One-column row holding the serialised record.
		"""
		return (self.str_stored,)

	def __enter__(self) -> RecordingCursor:
		"""Support ``with conn.cursor() as cur`` (psycopg).

		Returns
		-------
		RecordingCursor
			This cursor.
		"""
		return self

	def __exit__(self, *args: object) -> None:
		"""Close the ``with`` block.

		Parameters
		----------
		*args : object
			Exception triple, ignored.
		"""


class RecordingConnection:
	"""Connection stand-in handing out one :class:`RecordingCursor`."""

	def __init__(self, list_sql: list[str], str_stored: str) -> None:
		"""Build the connection's single cursor.

		Parameters
		----------
		list_sql : list of str
			Log every executed statement is appended to.
		str_stored : str
			Serialised record the ``SELECT`` returns.
		"""
		self.cls_cursor = RecordingCursor(list_sql, str_stored)

	def cursor(self) -> RecordingCursor:
		"""Return this connection's cursor.

		Returns
		-------
		RecordingCursor
			The recording cursor.
		"""
		return self.cls_cursor

	def commit(self) -> None:
		"""Accept a commit; nothing is persisted."""

	def __enter__(self) -> RecordingConnection:
		"""Support ``with self._connect() as conn``.

		Returns
		-------
		RecordingConnection
			This connection.
		"""
		return self

	def __exit__(self, *args: object) -> None:
		"""Close the ``with`` block.

		Parameters
		----------
		*args : object
			Exception triple, ignored.
		"""


def _build_handler(str_target: str) -> DatabaseHandler:
	"""Instantiate a handler without its ``__init__`` (which needs a live driver).

	Parameters
	----------
	str_target : str
		``<module stem>.<class name>`` inside ``chassis.db_schema.infrastructure``.

	Returns
	-------
	DatabaseHandler
		Handler carrying only the attributes ``update`` reads.
	"""
	str_module, str_class = str_target.split(".")
	cls_module = importlib.import_module(f"chassis.db_schema.infrastructure.{str_module}")
	cls_handler = object.__new__(getattr(cls_module, str_class))
	cls_handler.table = "records"
	cls_handler.id_field = "id"
	return cls_handler


def _open_connection(
	list_connects: list[str],
	list_sql: list[str],
	str_stored: str,
) -> RecordingConnection:
	"""Open one recording connection, logging that a connection was opened.

	Bound with :func:`functools.partial` to stand in for a handler's ``_connect``.

	Parameters
	----------
	list_connects : list of str
		Log one entry is appended to per connection opened.
	list_sql : list of str
		Log every executed statement is appended to.
	str_stored : str
		Serialised record the ``SELECT`` returns.

	Returns
	-------
	RecordingConnection
		A fresh recording connection.
	"""
	list_connects.append("opened")
	return RecordingConnection(list_sql, str_stored)


@pytest.fixture
def cls_sqlite_handler(tmp_path: Path) -> SQLiteDatabaseHandler:
	"""Create a SQLite handler holding one record with two independent fields.

	Parameters
	----------
	tmp_path : pathlib.Path
		Pytest temporary directory.

	Returns
	-------
	SQLiteDatabaseHandler
		Handler seeded with ``r1``.
	"""
	cls_handler = SQLiteDatabaseHandler(tmp_path / "records.db")
	cls_handler.create({"id": STR_RECORD_ID, "alpha": "initial", "beta": "initial"})
	return cls_handler


def test_sqlite_update_interleaved_writers_keep_both_fields(
	cls_sqlite_handler: SQLiteDatabaseHandler,
	monkeypatch: pytest.MonkeyPatch,
) -> None:
	"""Two threads writing different fields of one record must both survive.

	Parameters
	----------
	cls_sqlite_handler : SQLiteDatabaseHandler
		Handler seeded with ``r1``.
	monkeypatch : pytest.MonkeyPatch
		Used to stall the handler's JSON decode, widening the race window.
	"""
	monkeypatch.setattr(
		sqlite_handler, "json", SimpleNamespace(loads=_stalling_loads, dumps=json.dumps)
	)
	cls_barrier = threading.Barrier(2)
	cls_alpha = threading.Thread(
		target=_update_one_field, args=(cls_sqlite_handler, "alpha", cls_barrier)
	)
	cls_beta = threading.Thread(
		target=_update_one_field, args=(cls_sqlite_handler, "beta", cls_barrier)
	)
	cls_alpha.start()
	cls_beta.start()
	cls_alpha.join()
	cls_beta.join()
	monkeypatch.undo()
	assert cls_sqlite_handler.read(STR_RECORD_ID) == {
		"id": STR_RECORD_ID,
		"alpha": "written",
		"beta": "written",
	}


@pytest.mark.parametrize(("str_target", "str_lock"), sorted(DICT_LOCKED_SELECT.items()))
def test_update_reads_and_writes_one_locked_transaction(str_target: str, str_lock: str) -> None:
	"""The read and the write share one connection, and the read takes the row lock.

	Parameters
	----------
	str_target : str
		``<module stem>.<class name>`` of the handler under test.
	str_lock : str
		Fragment that dialect's locked ``SELECT`` must carry.
	"""
	cls_handler = _build_handler(str_target)
	list_connects: list[str] = []
	list_sql: list[str] = []
	str_stored = json.dumps({"id": STR_RECORD_ID, "alpha": "initial", "beta": "initial"})
	cls_handler._connect = partial(_open_connection, list_connects, list_sql, str_stored)  # noqa: SLF001
	dict_updated = cls_handler.update(STR_RECORD_ID, {"beta": "written"})
	assert (len(list_connects), str_lock in list_sql[0], list_sql[1][:6], dict_updated) == (
		1,
		True,
		"UPDATE",
		{"id": STR_RECORD_ID, "alpha": "initial", "beta": "written"},
	)
