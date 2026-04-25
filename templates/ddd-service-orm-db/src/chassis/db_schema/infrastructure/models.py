"""SQLAlchemy ORM models for the example Record entity."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, generate_uuid


class RecordModel(Base):
    """SQLAlchemy model for a generic Record entity.

    This is an example model demonstrating SQLAlchemy ORM patterns.
    Replace or extend this model based on your domain requirements.

    Attributes
    ----------
    id : str
        Primary key, auto-generated UUID.
    data : str
        JSON-serialized payload or text content.
    created_at : datetime
        Timestamp when the record was created.
    updated_at : datetime
        Timestamp when the record was last updated.
    """

    __tablename__ = "records"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=generate_uuid
    )
    data: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<RecordModel(id={self.id!r}, created_at={self.created_at})>"

    def to_dict(self) -> dict:
        """Convert model to dictionary representation.

        Returns
        -------
        dict
            Dictionary with all model fields.
        """
        return {
            "id": self.id,
            "data": self.data,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
