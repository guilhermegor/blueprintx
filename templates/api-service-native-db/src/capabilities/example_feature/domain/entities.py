"""Persistence entities for the example_feature capability."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid

from .enums import NoteStatus


@dataclass
class Note:
    """Note entity — maps to a database row."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    title: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    status: NoteStatus = NoteStatus.DRAFT
