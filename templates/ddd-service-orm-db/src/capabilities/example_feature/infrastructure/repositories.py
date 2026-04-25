"""Concrete repository implementations for the example feature."""

from __future__ import annotations

from typing import Iterable

from ..domain.entities import Note


class InMemoryNoteRepository:
	"""In-memory repository for quick starts and tests."""

	def __init__(self) -> None:
		self._dict_items: dict[str, Note] = {}

	def add(self, cls_note: Note) -> Note:
		"""Persist a note and return it."""
		self._dict_items[cls_note.id] = cls_note
		return cls_note

	def get(self, str_note_id: str) -> Note | None:
		"""Return the note with the given id, or None."""
		return self._dict_items.get(str_note_id)

	def list(self) -> Iterable[Note]:
		"""Return all stored notes."""
		return self._dict_items.values()
