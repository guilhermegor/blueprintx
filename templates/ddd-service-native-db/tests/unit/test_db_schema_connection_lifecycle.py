"""Connection-lifecycle and identifier regression tests for the ``db_schema`` handlers (#646).

Two defects, one file because both live in the six handlers' shared shape:

1. **Connections never closed.** For ``sqlite3`` and ``pyodbc``, ``with conn:`` commits or rolls
   back the transaction and does NOT close the connection, so every handler call leaked one
   until garbage collection (on SQLite, also holding the file lock). ``psycopg``,
   ``mysql.connector`` and ``oracledb`` close the connection in ``__exit__`` already, which is
   why only the SQLite and SQL Server handlers needed ``contextlib.closing``.
2. **Unvalidated identifiers.** ``table`` and ``id_field`` are interpolated into SQL text, because
   a driver cannot bind an identifier. They are validated once, in each constructor.
"""

from __future__ import annotations

from contextlib import suppress
import importlib
import json
from pathlib import Path
import sqlite3

import pytest

from chassis.db.infrastructure.helpers import validate_sql_identifier
from chassis.db_schema.infrastructure.mssql_handler import MSSQLDatabaseHandler
from chassis.db_schema.infrastructure.sqlite_handler import SQLiteDatabaseHandler


STR_RECORD_ID = "r1"
STR_STORED = json.dumps({"id": STR_RECORD_ID, "alpha": "initial"})

# Operation name -> callable(handler, tmp_path). Every public method that opens a connection.
DICT_OPERATIONS = {
    "create": lambda cls_handler, path_dir: cls_handler.create({"id": STR_RECORD_ID}),
    "read": lambda cls_handler, path_dir: cls_handler.read(STR_RECORD_ID),
    "update": lambda cls_handler, path_dir: cls_handler.update(STR_RECORD_ID, {"beta": "x"}),
    "delete": lambda cls_handler, path_dir: cls_handler.delete(STR_RECORD_ID),
}

# (module stem, class name, driver attribute or None, constructor args before the identifiers).
LIST_HANDLERS = [
    ("sqlite_handler", "SQLiteDatabaseHandler", None, ("unused.db",)),
    ("mssql_handler", "MSSQLDatabaseHandler", "pyodbc", ("DSN=x",)),
    ("postgres_handler", "PostgresDatabaseHandler", "psycopg", ("postgresql://u:p@h/db",)),
    ("mysql_handler", "MySQLDatabaseHandler", "mysql_connector", ("mysql://u:p@h/db",)),
    ("mariadb_handler", "MariaDBDatabaseHandler", "mysql_connector", ("mariadb://u:p@h/db",)),
    ("oracle_handler", "OracleDatabaseHandler", "oracledb", ("dsn",)),
]


class PyodbcLikeCursor:
    """Cursor stand-in returning one stored row."""

    rowcount = 1

    def execute(self, str_sql: str, *args: object) -> None:
        """Accept a statement; nothing is executed.

        Parameters
        ----------
        str_sql : str
            Statement text, ignored.
        *args : object
            Bound parameters, ignored.
        """

    def fetchone(self) -> tuple[str]:
        """Return the single stored row.

        Returns
        -------
        tuple of str
            One-column row holding the serialised record.
        """
        return (STR_STORED,)

    def __iter__(self) -> object:
        """Iterate the single stored row, as ``backup`` does.

        Returns
        -------
        iterator
            Iterator over one-column rows.
        """
        return iter([(STR_STORED,)])


class PyodbcLikeConnection:
    """Connection with pyodbc's context-manager contract: commit on exit, never close."""

    def __init__(self) -> None:
        """Start open."""
        self.bool_closed = False

    def cursor(self) -> PyodbcLikeCursor:
        """Return a cursor.

        Returns
        -------
        PyodbcLikeCursor
            A fresh cursor.
        """
        return PyodbcLikeCursor()

    def commit(self) -> None:
        """Accept a commit; nothing is persisted."""

    def close(self) -> None:
        """Mark the connection closed."""
        self.bool_closed = True

    def __enter__(self) -> PyodbcLikeConnection:
        """Enter the transaction block, as pyodbc does.

        Returns
        -------
        PyodbcLikeConnection
            This connection.
        """
        return self

    def __exit__(self, *args: object) -> None:
        """Leave the block WITHOUT closing, which is the behaviour under test.

        Parameters
        ----------
        *args : object
            Exception triple, ignored.
        """


def _open_connections(list_made: list, cls_factory: object) -> object:
    """Build a ``_connect`` replacement that records every connection it hands out.

    Parameters
    ----------
    list_made : list
        Receives each connection opened.
    cls_factory : callable
        Opens the real or fake connection.

    Returns
    -------
    callable
        Zero-argument stand-in for a handler's ``_connect``.
    """

    def _connect() -> object:
        cls_conn = cls_factory()
        list_made.append(cls_conn)
        return cls_conn

    return _connect


def _sqlite_is_open(cls_conn: sqlite3.Connection) -> bool:
    """Report whether a SQLite connection still accepts statements.

    A closed connection raises ``ProgrammingError`` on any use, so the probe records success
    only when the statement ran.

    Parameters
    ----------
    cls_conn : sqlite3.Connection
        Connection to probe.

    Returns
    -------
    bool
        ``True`` when the connection is open.
    """
    list_ran: list[str] = []
    with suppress(sqlite3.ProgrammingError):
        cls_conn.execute("SELECT 1")
        list_ran.append("ran")
    return bool(list_ran)


@pytest.mark.parametrize("str_operation", sorted(DICT_OPERATIONS))
def test_sqlite_handler_closes_every_connection_it_opens(
    str_operation: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After any SQLite handler call, every connection it opened is closed.

    Parameters
    ----------
    str_operation : str
        Name of the handler method under test.
    tmp_path : pathlib.Path
        Pytest temporary directory holding the database file.
    monkeypatch : pytest.MonkeyPatch
        Swaps ``_connect`` for a recording version, after construction.
    """
    cls_handler = SQLiteDatabaseHandler(tmp_path / "records.db")
    cls_handler.create({"id": STR_RECORD_ID, "alpha": "initial"})
    list_made: list[sqlite3.Connection] = []
    monkeypatch.setattr(
        cls_handler,
        "_connect",
        _open_connections(list_made, lambda: sqlite3.connect(cls_handler.db_path)),
    )

    DICT_OPERATIONS[str_operation](cls_handler, tmp_path)

    list_open = [cls_conn for cls_conn in list_made if _sqlite_is_open(cls_conn)]
    assert list_open == [], f"{str_operation} left {len(list_open)} connection(s) open"


@pytest.mark.parametrize("str_operation", [*sorted(DICT_OPERATIONS), "backup"])
def test_mssql_handler_closes_every_connection_it_opens(
    str_operation: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After any SQL Server handler call, every connection it opened is closed.

    Parameters
    ----------
    str_operation : str
        Name of the handler method under test (``backup`` included, it streams rows).
    tmp_path : pathlib.Path
        Pytest temporary directory, the backup target.
    monkeypatch : pytest.MonkeyPatch
        Swaps ``_connect`` for a recording pyodbc-like fake.
    """
    cls_handler = object.__new__(MSSQLDatabaseHandler)
    cls_handler.table = "records"
    cls_handler.id_field = "id"
    list_made: list[PyodbcLikeConnection] = []
    monkeypatch.setattr(
        cls_handler, "_connect", _open_connections(list_made, PyodbcLikeConnection)
    )
    dict_calls = {
        **DICT_OPERATIONS,
        "backup": lambda cls_h, path_dir: cls_h.backup(path_dir / "backup.json"),
    }

    dict_calls[str_operation](cls_handler, tmp_path)

    list_open = [cls_conn for cls_conn in list_made if not cls_conn.bool_closed]
    assert list_open == [], f"{str_operation} left {len(list_open)} connection(s) open"


@pytest.mark.parametrize("str_value", ["records", "_t", "Table_2", "a"])
def test_a_plain_identifier_is_accepted(str_value: str) -> None:
    """Letters, digits and underscores, not starting with a digit, pass.

    Parameters
    ----------
    str_value : str
        Identifier that must be accepted.
    """
    assert validate_sql_identifier(str_value, "table") is None


@pytest.mark.parametrize(
    "str_value",
    ["", "1abc", "a b", "a-b", "a;DROP TABLE x", "a.b", "records\n", "t'", 'a"b', "ünï"],
)
def test_an_unsafe_identifier_is_rejected_naming_the_field(str_value: str) -> None:
    """Anything outside ``[A-Za-z_][A-Za-z0-9_]*`` raises, and the message names the field.

    Parameters
    ----------
    str_value : str
        Identifier that must be rejected.
    """
    with pytest.raises(ValueError, match="id_field must match"):
        validate_sql_identifier(str_value, "id_field")


@pytest.mark.parametrize(("str_stem", "str_class", "str_driver", "tuple_args"), LIST_HANDLERS)
@pytest.mark.parametrize("dict_bad", [{"table": "t; DROP TABLE x"}, {"id_field": "id--"}])
def test_every_handler_rejects_an_unsafe_identifier_before_touching_the_driver(
    str_stem: str,
    str_class: str,
    str_driver: str | None,
    tuple_args: tuple,
    dict_bad: dict,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The constructor raises ``ValueError`` before any statement is built or connection made.

    The driver module is replaced by a bare sentinel, so reaching it would raise something
    other than ``ValueError``; that is what proves the validation runs first.

    Parameters
    ----------
    str_stem : str
        Handler module stem inside ``chassis.db_schema.infrastructure``.
    str_class : str
        Handler class name.
    str_driver : str or None
        Module attribute holding the optional driver, patched to a sentinel.
    tuple_args : tuple
        Leading constructor arguments.
    dict_bad : dict
        The unsafe ``table`` or ``id_field`` keyword.
    monkeypatch : pytest.MonkeyPatch
        Replaces the driver attribute.
    """
    cls_module = importlib.import_module(f"chassis.db_schema.infrastructure.{str_stem}")
    if str_driver is not None:
        monkeypatch.setattr(cls_module, str_driver, object())

    with pytest.raises(ValueError, match="must match"):
        getattr(cls_module, str_class)(*tuple_args, **dict_bad)
