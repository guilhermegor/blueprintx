"""Concrete repository implementations for the example feature."""

from __future__ import annotations

from typing import Iterable

from ..domain.entities import Note
from ..domain.ports import NoteRepository


class InMemoryNoteRepository(NoteRepository):
    """In-memory repository for quick starts and tests."""

    def __init__(self):
        self._items: dict[str, Note] = {}

    def add(self, note: Note) -> Note:
        self._items[note.id] = note
        return note

    def get(self, note_id: str) -> Note | None:
        return self._items.get(note_id)

    def list(self) -> Iterable[Note]:
        return self._items.values()
