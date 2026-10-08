"""Unit tests for ``ExampleEntity`` (native DB-API model) against a real SQLite file.

The model is the one place that knows the cursor-to-frame projection, so these tests run it
against a throwaway SQLite database in ``tmp_path`` rather than mocking the cursor: a mock
would assert that the code calls the driver, not that a row actually comes back typed.
``fetch_all`` also runs through the ``TypeChecker`` metaclass here, which is the call that
used to raise a forward-reference exception while ``pandas`` was imported only for typing.
"""

from collections.abc import Iterator
from pathlib import Path
import sqlite3

import pandas as pd
import pytest

from model.example_entity import ExampleEntity


# --------------------------
# Fixtures
# --------------------------
@pytest.fixture
def cls_connection(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    """Provide a connection to a throwaway SQLite database file.

    Parameters
    ----------
    tmp_path : pathlib.Path
            Pytest-provided temporary directory.

    Yields
    ------
    sqlite3.Connection
            Connection for ``tmp_path / "example.db"``, closed after the test.
    """
    cls_built = sqlite3.connect(tmp_path / "example.db")
    yield cls_built
    cls_built.close()


@pytest.fixture
def cls_entity(cls_connection: sqlite3.Connection) -> ExampleEntity:
    """Provide an entity whose table already exists.

    Parameters
    ----------
    cls_connection : sqlite3.Connection
            Connection to the throwaway database.

    Returns
    -------
    ExampleEntity
            Entity with ``ensure_table()`` already applied.
    """
    cls_built = ExampleEntity(cls_connection)
    cls_built.ensure_table()
    return cls_built


# --------------------------
# Tests
# --------------------------
def test_fetch_all_passes_the_type_checker_on_the_frame_annotation(
    cls_entity: ExampleEntity,
) -> None:
    """``fetch_all`` returns a real ``pd.DataFrame`` through the ``TypeChecker`` metaclass."""
    assert isinstance(cls_entity.fetch_all(), pd.DataFrame)


def test_ensure_table_is_idempotent(cls_entity: ExampleEntity) -> None:
    """A second ``ensure_table`` call neither raises nor drops existing rows."""
    cls_entity.insert("kept")
    cls_entity.ensure_table()

    assert len(cls_entity.fetch_all()) == 1


def test_insert_then_fetch_all_returns_the_inserted_title(cls_entity: ExampleEntity) -> None:
    """A row written by ``insert`` comes back through ``fetch_all``."""
    cls_entity.insert("alpha")

    assert cls_entity.fetch_all()["title"].tolist() == ["alpha"]


def test_insert_assigns_incrementing_ids(cls_entity: ExampleEntity) -> None:
    """The autoincrement primary key numbers rows in insert order."""
    cls_entity.insert("alpha")
    cls_entity.insert("beta")

    assert cls_entity.fetch_all()["id"].tolist() == [1, 2]


def test_fetch_all_types_the_columns_as_declared(cls_entity: ExampleEntity) -> None:
    """``fetch_all`` applies the declared dtypes instead of letting pandas infer them."""
    cls_entity.insert("alpha")

    assert cls_entity.fetch_all()["id"].dtype == "int64"


def test_fetch_all_on_an_empty_table_keeps_the_declared_columns(
    cls_entity: ExampleEntity,
) -> None:
    """An empty table still yields a frame with the declared columns, not a bare one."""
    assert list(cls_entity.fetch_all().columns) == ["id", "title"]
