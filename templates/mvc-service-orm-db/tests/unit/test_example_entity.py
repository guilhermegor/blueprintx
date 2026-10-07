"""Unit tests for ``ExampleEntity`` (SQLAlchemy ORM model) against a real SQLite file.

The model is the one place that knows the ORM-to-frame projection, so these tests run it
against a throwaway SQLite database in ``tmp_path`` rather than mocking the session: a mock
would assert that the code calls the ORM, not that a row actually comes back typed.
"""

from pathlib import Path

import pandas as pd
import pytest
from sqlalchemy import Engine, create_engine, inspect

from src.model.example_entity import ExampleEntity


# --------------------------
# Fixtures
# --------------------------
@pytest.fixture
def cls_engine(tmp_path: Path) -> Engine:
    """Provide an engine bound to a throwaway SQLite database file.

    Parameters
    ----------
    tmp_path : pathlib.Path
            Pytest-provided temporary directory.

    Returns
    -------
    sqlalchemy.Engine
            Engine for ``tmp_path / "example.db"``, disposed after the test.
    """
    cls_built = create_engine(f"sqlite:///{tmp_path / 'example.db'}")
    yield cls_built
    cls_built.dispose()


@pytest.fixture
def cls_entity(cls_engine: Engine) -> ExampleEntity:
    """Provide an entity whose table already exists.

    Parameters
    ----------
    cls_engine : sqlalchemy.Engine
            Engine bound to the throwaway database.

    Returns
    -------
    ExampleEntity
            Entity with ``ensure_table()`` already applied.
    """
    cls_built = ExampleEntity(cls_engine)
    cls_built.ensure_table()
    return cls_built


# --------------------------
# Tests
# --------------------------
def test_ensure_table_creates_the_example_table(cls_engine: Engine) -> None:
    """``ensure_table`` creates the ``example`` table in an empty database."""
    ExampleEntity(cls_engine).ensure_table()

    assert inspect(cls_engine).has_table("example")


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
    df_empty: pd.DataFrame = cls_entity.fetch_all()

    assert list(df_empty.columns) == ["id", "title"]
