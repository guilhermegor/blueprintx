"""Ports (interfaces) the domain expects infrastructure to implement."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable

from .entities import Note


class NoteRepository(ABC):
    """Repository port for persisting notes."""

    @abstractmethod
    def add(self, note: Note) -> Note:
        """Persist a note and return it."""

    @abstractmethod
    def get(self, note_id: str) -> Note | None:
        """Fetch a note by identifier."""

    @abstractmethod
    def list(self) -> Iterable[Note]:
        """Return all notes."""
