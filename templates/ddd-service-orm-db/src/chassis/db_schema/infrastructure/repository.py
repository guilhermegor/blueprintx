"""Generic SQLAlchemy repository implementation."""

from __future__ import annotations

import json
from typing import Optional

from sqlalchemy.orm import Session

from .base import Repository, generate_uuid
from .models import RecordModel


class SQLAlchemyRecordRepository(Repository):
    """SQLAlchemy-based repository for Record entities.

    This repository provides CRUD operations using SQLAlchemy ORM.
    It works with any database supported by SQLAlchemy (PostgreSQL,
    MySQL, SQLite, Oracle, MSSQL, etc.).

    Parameters
    ----------
    session : Session
        SQLAlchemy session for database operations.

    Examples
    --------
    >>> from core.infrastructure.database import DatabaseSession, SQLAlchemyRecordRepository
    >>> db = DatabaseSession("sqlite:///app.db")
    >>> db.create_tables()
    >>> with db.session() as session:
    ...     repo = SQLAlchemyRecordRepository(session)
    ...     record_id = repo.add({"title": "Hello", "content": "World"})
    ...     session.commit()
    """

    def __init__(self, session: Session):
        super().__init__(session)

    def add(self, entity: dict) -> str:
        """Add a new record to the database.

        Parameters
        ----------
        entity : dict
            Dictionary containing record data.

        Returns
        -------
        str
            ID of the created record.
        """
        record_id = entity.get("id") or generate_uuid()
        record = RecordModel(
            id=record_id,
            data=json.dumps(entity),
        )
        self.session.add(record)
        self.session.flush()
        return record.id

    def get(self, entity_id: str) -> Optional[dict]:
        """Retrieve a record by ID.

        Parameters
        ----------
        entity_id : str
            Unique identifier of the record.

        Returns
        -------
        dict or None
            Record data if found, otherwise ``None``.
        """
        record = self.session.get(RecordModel, entity_id)
        if record is None:
            return None
        return json.loads(record.data) if record.data else {"id": record.id}

    def update(self, entity: dict) -> Optional[dict]:
        """Update an existing record.

        Parameters
        ----------
        entity : dict
            Dictionary containing record data with ``id`` field.

        Returns
        -------
        dict or None
            Updated record data if found, otherwise ``None``.
        """
        entity_id = entity.get("id")
        if not entity_id:
            return None

        record = self.session.get(RecordModel, entity_id)
        if record is None:
            return None

        record.data = json.dumps(entity)
        self.session.flush()
        return entity

    def delete(self, entity_id: str) -> bool:
        """Delete a record by ID.

        Parameters
        ----------
        entity_id : str
            Unique identifier of the record to delete.

        Returns
        -------
        bool
            ``True`` if record was deleted, ``False`` if not found.
        """
        record = self.session.get(RecordModel, entity_id)
        if record is None:
            return False
        self.session.delete(record)
        self.session.flush()
        return True

    def list_all(self) -> list[dict]:
        """Retrieve all records.

        Returns
        -------
        list[dict]
            List of all record data dictionaries.
        """
        records = self.session.query(RecordModel).all()
        return [
            json.loads(r.data) if r.data else {"id": r.id}
            for r in records
        ]
