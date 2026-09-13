"""Example service-style model.

Demonstrates the MVC model pattern with native drivers: take a DB-API connection, issue raw
SQL, and hand the cursor to the frame seam. Copy this file per domain entity and adapt the
table name and columns.

Note what this file does NOT do: it never calls the pandas API. ``pandas`` appears only as
the return **annotation**, which is the vocabulary the layers agree on — the construction
lives in ``utils.frames``. Copying this file therefore propagates the boundary rather than a
direct vendor call, which is the point of a reference example.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from utils.frames import from_cursor
from utils.typing import TypeChecker


if TYPE_CHECKING:
    import pandas as pd


# Declare the column types on load — never trust pandas' inference (a zero-padded
# code becomes an int, a mixed column becomes object). Adjust per entity.
_DICT_DTYPES: dict[str, str] = {"id": "int64", "title": "str"}


class ExampleEntity(metaclass=TypeChecker):
    """Read/write access to a single example table.

    Parameters
    ----------
    cls_connection : Any
            An open DB-API 2.0 connection (see :func:`config.connection_db.build_connection`).
    str_table : str, optional
            Table name to operate on, by default ``"example"``.
    """

    def __init__(self, cls_connection: Any, str_table: str = "example") -> None:
        self.cls_connection = cls_connection
        self.str_table = str_table

    def ensure_table(self) -> None:
        """Create the example table if it does not already exist."""
        cls_cursor = self.cls_connection.cursor()
        # noqa justified: str_table is a developer-controlled identifier, never user input.
        cls_cursor.execute(  # noqa: S608
            f"CREATE TABLE IF NOT EXISTS {self.str_table} "
            "(id INTEGER PRIMARY KEY, title TEXT NOT NULL)"
        )
        self.cls_connection.commit()
        cls_cursor.close()

    def insert(self, str_title: str) -> None:
        """Insert one row into the example table.

        Parameters
        ----------
        str_title : str
                Value for the ``title`` column.
        """
        cls_cursor = self.cls_connection.cursor()
        # noqa justified: str_table is a developer-controlled identifier, never user input.
        cls_cursor.execute(
            f"INSERT INTO {self.str_table} (title) VALUES (?)",  # noqa: S608
            (str_title,),
        )
        self.cls_connection.commit()
        cls_cursor.close()

    def fetch_all(self) -> pd.DataFrame:
        """Read every row from the example table into a DataFrame.

        Returns
        -------
        pd.DataFrame
                One row per record, every declared column typed.
        """
        cls_cursor = self.cls_connection.cursor()
        try:
            cls_cursor.execute(f"SELECT * FROM {self.str_table}")  # noqa: S608
            return from_cursor(cls_cursor, _DICT_DTYPES)
        finally:
            cls_cursor.close()
