"""Domain use-cases for the example_feature capability.

Operate exclusively on domain entities and port interfaces — no DTOs, no I/O libs.
"""

from __future__ import annotations

from ..domain.entities import Note
from ..domain.ports import NoteRepository


class CreateNote:
	"""Persist a new note via the repository port."""

	def __init__(self, cls_repo: NoteRepository) -> None:
		self._cls_repo = cls_repo

	def execute(self, cls_note: Note) -> Note:
		"""Save and return the persisted note."""
		return self._cls_repo.add(cls_note)


class ListNotes:
	"""Retrieve all notes from the repository."""

	def __init__(self, cls_repo: NoteRepository) -> None:
		self._cls_repo = cls_repo

	def execute(self) -> list[Note]:
		"""Return all stored notes."""
		return list(self._cls_repo.list())
