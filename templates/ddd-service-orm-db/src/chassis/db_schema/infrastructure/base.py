"""SQLAlchemy database abstraction layer."""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Generator
from typing import Generic, TypeVar
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from chassis.typing import ABCTypeCheckerMeta


class Base(DeclarativeBase):
	"""SQLAlchemy declarative base for all ORM models."""

	pass


def generate_uuid() -> str:
	"""Generate a unique identifier string.

	Returns
	-------
	str
		Hex UUID string.
	"""
	return uuid.uuid4().hex


class DatabaseSession:
	"""SQLAlchemy session manager for database operations.

	Parameters
	----------
	database_url : str
		SQLAlchemy connection URL (e.g., ``postgresql://user:pass@host/db``).
	echo : bool, optional
		If ``True``, log all SQL statements, by default ``False``.

	Examples
	--------
	>>> db = DatabaseSession("sqlite:///app.db")
	>>> with db.session() as session:
	...     session.add(some_model)
	...     session.commit()
	"""

	def __init__(self, database_url: str, echo: bool = False) -> None:
		self.engine = create_engine(database_url, echo=echo)
		self._session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)

	def create_tables(self) -> None:
		"""Create all tables defined in the ORM models."""
		Base.metadata.create_all(self.engine)

	def drop_tables(self) -> None:
		"""Drop all tables defined in the ORM models."""
		Base.metadata.drop_all(self.engine)

	def session(self) -> Session:
		"""Create a new database session.

		Returns
		-------
		Session
			SQLAlchemy session bound to the engine.
		"""
		return self._session_factory()

	def get_session(self) -> Generator[Session, None, None]:
		"""Yield a database session for dependency injection.

		Yields
		------
		Session
			SQLAlchemy session that auto-closes after use.

		Examples
		--------
		For use with FastAPI dependency injection:

		>>> @app.get("/items")
		... def get_items(session: Session = Depends(db.get_session)):
		...     return session.query(Item).all()
		"""
		session = self._session_factory()
		try:
			yield session
		finally:
			session.close()


_EntityT = TypeVar("_EntityT")


class Repository(Generic[_EntityT], metaclass=ABCTypeCheckerMeta):
	"""Abstract repository for ORM-based data access.

	Generic over the entity shape a concrete implementation persists (e.g. a
	dataclass, or the ``dict`` blob ``SQLAlchemyRecordRepository`` stores) —
	parameterize a subclass as ``Repository[MyEntity]`` to type its CRUD
	methods precisely; an unparameterized subclass keeps them ``Any``-typed.

	Parameters
	----------
	session : Session
		SQLAlchemy session for database operations.
	"""

	def __init__(self, session: Session) -> None:
		self.session = session

	@abstractmethod
	def add(self, entity: _EntityT) -> _EntityT:
		"""Add an entity to the repository.

		Parameters
		----------
		entity : _EntityT
			Entity to persist.

		Returns
		-------
		_EntityT
			Persisted entity with assigned identifier.
		"""

	@abstractmethod
	def get(self, entity_id: str) -> _EntityT | None:
		"""Retrieve an entity by identifier.

		Parameters
		----------
		entity_id : str
			Unique identifier.

		Returns
		-------
		_EntityT or None
			Entity if found, otherwise ``None``.
		"""

	@abstractmethod
	def update(self, entity: _EntityT) -> _EntityT | None:
		"""Update an existing entity.

		Parameters
		----------
		entity : _EntityT
			Entity with updated fields.

		Returns
		-------
		_EntityT or None
			Updated entity if it exists, otherwise ``None``.
		"""

	@abstractmethod
	def delete(self, entity_id: str) -> bool:
		"""Remove an entity by identifier.

		Parameters
		----------
		entity_id : str
			Unique identifier of the entity to remove.

		Returns
		-------
		bool
			``True`` if entity was deleted, ``False`` otherwise.
		"""

	@abstractmethod
	def list_all(self) -> list[_EntityT]:
		"""Retrieve all entities.

		Returns
		-------
		list[_EntityT]
			All entities in the repository.
		"""
