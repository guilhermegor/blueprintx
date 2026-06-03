"""Example service-style model (SQLAlchemy ORM).

Demonstrates the MVC model pattern with the ORM: a declarative model plus a
service class that opens sessions, runs queries, and shapes results into a
pandas DataFrame via ``pd.read_sql``. Copy and adapt per domain entity.
"""

from __future__ import annotations

import pandas as pd
from sqlalchemy import Engine, String, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from utils.dtypes import apply_dtypes


# Declare the column types on load — never trust pandas' inference (a zero-padded
# code becomes an int, a mixed column becomes object). Adjust per entity.
_DICT_DTYPES: dict[str, str] = {"id": "int64", "title": "str"}


class Base(DeclarativeBase):
	"""Declarative base for the example model."""


class ExampleRecord(Base):
	"""ORM model mapped to the ``example`` table."""

	__tablename__ = "example"

	id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
	title: Mapped[str] = mapped_column(String(255), nullable=False)


class ExampleEntity:
	"""Read/write access to the example table via SQLAlchemy ORM.

	Parameters
	----------
	cls_engine : sqlalchemy.Engine
		Engine bound to the target database (see
		:func:`config.connection_db.build_engine`).
	"""

	def __init__(self, cls_engine: Engine) -> None:
		self.cls_engine = cls_engine
		self._session_factory = sessionmaker(bind=cls_engine, expire_on_commit=False)

	def ensure_table(self) -> None:
		"""Create the example table if it does not already exist."""
		Base.metadata.create_all(self.cls_engine)

	def insert(self, str_title: str) -> None:
		"""Insert one row into the example table.

		Parameters
		----------
		str_title : str
			Value for the ``title`` column.
		"""
		cls_session = self._session_factory()
		try:
			cls_session.add(ExampleRecord(title=str_title))
			cls_session.commit()
		finally:
			cls_session.close()

	def fetch_all(self) -> pd.DataFrame:
		"""Read every row from the example table into a DataFrame.

		Returns
		-------
		pd.DataFrame
			One row per record.
		"""
		with self.cls_engine.connect() as cls_conn:
			df_records = pd.read_sql(select(ExampleRecord), cls_conn)
		return apply_dtypes(df_records, dict_dtypes=_DICT_DTYPES)
