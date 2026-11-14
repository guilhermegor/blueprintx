"""Structural DB-API 2.0 types shared by every layer that touches a connection.

Drivers (``sqlite3``, ``psycopg``, ``mysql.connector``, ``pyodbc``, ``oracledb``) do not share a
base class, so a connection used to be typed ``Any``. These ``Protocol`` classes name the
subset of PEP 249 the template actually calls, so a misuse (a missing ``commit``, a typo in
``fetchone``) is a type error while any driver's object is still accepted.

A row cell is ``object``, never ``Any``: the caller narrows before use.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from types import TracebackType
from typing import Protocol, Self, runtime_checkable


QueryParams = Sequence[object] | Mapping[str, object]
Row = Sequence[object]


@runtime_checkable
class DbResultCursor(Protocol):
    """The part of a cursor needed to read an executed query's result."""

    @property
    def description(self) -> Sequence[Sequence[object]] | None:
        """Column metadata of the last query, ``None`` when it returned no rows."""
        ...

    def fetchall(self) -> Sequence[Row]:
        """Return every remaining row."""
        ...


@runtime_checkable
class DbCursor(DbResultCursor, Protocol):
    """The cursor surface the template calls."""

    @property
    def rowcount(self) -> int:
        """Rows affected by the last statement."""
        ...

    def execute(self, operation: str, parameters: QueryParams = ..., /) -> object:
        """Run one statement."""
        ...

    def fetchone(self) -> Row | None:
        """Return the next row, or ``None`` when exhausted."""
        ...

    def __iter__(self) -> Iterator[Row]:
        """Iterate the remaining rows."""
        ...

    def close(self) -> object:
        """Release the cursor."""
        ...


@runtime_checkable
class DbConnection(Protocol):
    """The connection surface the template calls."""

    def cursor(self) -> DbCursor:
        """Open a cursor."""
        ...

    def commit(self) -> object:
        """Commit the open transaction."""
        ...

    def close(self) -> object:
        """Release the connection."""
        ...


@runtime_checkable
class DbManagedCursor(DbCursor, Protocol):
    """A cursor usable as a context manager (``with conn.cursor() as cur``)."""

    def __enter__(self) -> Self:
        """Enter the cursor scope."""
        ...

    def __exit__(
        self,
        type_exc: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
        /,
    ) -> object:
        """Leave the cursor scope."""
        ...


@runtime_checkable
class DbManagedConnection(DbConnection, Protocol):
    """A connection usable as a context manager (``with conn:``)."""

    def cursor(self) -> DbManagedCursor:
        """Open a context-manager cursor."""
        ...

    def __enter__(self) -> Self:
        """Enter the connection scope."""
        ...

    def __exit__(
        self,
        type_exc: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
        /,
    ) -> object:
        """Leave the connection scope."""
        ...
