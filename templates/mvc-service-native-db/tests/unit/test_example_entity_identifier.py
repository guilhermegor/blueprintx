"""``ExampleEntity`` validates its table name before it reaches SQL text (#646)."""

import sqlite3

import pytest

from model.example_entity import ExampleEntity


@pytest.mark.parametrize("str_table", ["example", "_t", "Table_2"])
def test_a_plain_table_name_builds_a_working_entity(str_table: str) -> None:
    """A plain identifier passes and the table can be created.

    Parameters
    ----------
    str_table : str
        Identifier that must be accepted.
    """
    cls_connection = sqlite3.connect(":memory:")
    ExampleEntity(cls_connection, str_table).ensure_table()
    tuple_row = cls_connection.execute(
        "SELECT name FROM sqlite_master WHERE name = ?", (str_table,)
    ).fetchone()
    cls_connection.close()

    assert tuple_row == (str_table,)


@pytest.mark.parametrize("str_table", ["", "1abc", "a b", "a;DROP TABLE x", "a.b", "t\n"])
def test_an_unsafe_table_name_is_rejected_before_any_sql(str_table: str) -> None:
    """Anything outside ``[A-Za-z_][A-Za-z0-9_]*`` raises in the constructor.

    Parameters
    ----------
    str_table : str
        Identifier that must be rejected.
    """
    with pytest.raises(ValueError, match="str_table must match"):
        ExampleEntity(sqlite3.connect(":memory:"), str_table)
