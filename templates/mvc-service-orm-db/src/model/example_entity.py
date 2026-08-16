"""Example service-style model (SQLAlchemy ORM).

Demonstrates the MVC model pattern with the ORM: a declarative model plus a service class
that opens sessions for writes and reads through the session, projecting mapped objects into
the frame seam. Copy and adapt per domain entity.

Note what this file does NOT do: it never calls the pandas API. ``pandas`` appears only as
the return **annotation**; the construction lives in ``utils.frames``. That matters here more
than anywhere else, because this file exists to be copied — the previous version called
``pd.read_sql``, which the project's own ``ruff.toml`` bans, and the gate had been silenced
for this path rather than the example fixed (blueprintx#172).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Engine, String, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from utils.frames import from_records
from utils.typing import TypeChecker


if TYPE_CHECKING:
	import pandas as pd


# Declare the column types on load — never trust pandas' inference (a zero-padded
# code becomes an int, a mixed column becomes object). Adjust per entity.
_DICT_DTYPES: dict[str, str] = {"id": "int64", "title": "str"}


# NB: SQLAlchemy declarative classes (Base, ExampleRecord) carry their own metaclass, so
# ``metaclass=TypeChecker`` would raise a metaclass conflict — only the plain service class
# below takes the runtime checker.
class Base(DeclarativeBase):
	"""Declarative base for the example model."""


class ExampleRecord(Base):
	"""ORM model mapped to the ``example`` table."""

	__tablename__ = "example"

	id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
	title: Mapped[str] = mapped_column(String(255), nullable=False)


class ExampleEntity(metaclass=TypeChecker):
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

		Reads through the ORM session and projects each mapped object into a plain mapping,
		then hands those to ``utils.frames.from_records``. The projection stays here because
		this is the only place that knows which attributes belong in the frame; the pandas
		call stays in the seam.

		Returns
		-------
		pd.DataFrame
			One row per record, every declared column typed.
		"""
		cls_session = self._session_factory()
		try:
			list_records = [
				{"id": cls_row.id, "title": cls_row.title}
				for cls_row in cls_session.scalars(select(ExampleRecord))
			]
		finally:
			cls_session.close()
		return from_records(list_records, _DICT_DTYPES)
