"""Concrete repository implementations for the example feature."""

from __future__ import annotations

from collections.abc import Iterable
import threading

from capabilities.example_feature.domain.entities import Note
from chassis.typing import TypeChecker


class InMemoryNoteRepository(metaclass=TypeChecker):
	"""In-memory repository for quick starts and tests."""

	def __init__(self) -> None:
		# One repository instance is shared by every request (AppContainer), and FastAPI
		# runs a synchronous handler in a worker thread — so these methods DO run
		# concurrently. See docs/architecture.md for why the lock is here and not in the
		# use case.
		self._dict_items: dict[str, Note] = {}
		self._cls_lock = threading.Lock()

	def add(self, cls_note: Note) -> Note:
		"""Persist a note and return it."""
		with self._cls_lock:
			self._dict_items[cls_note.id] = cls_note
		return cls_note

	def get(self, str_note_id: str) -> Note | None:
		"""Return the note with the given id, or None."""
		with self._cls_lock:
			return self._dict_items.get(str_note_id)

	def list(self) -> Iterable[Note]:
		"""Return a SNAPSHOT of all stored notes.

		⚠️ A live ``dict_values`` view is iterated by the caller AFTER this returns, so a
		concurrent ``add`` raises ``RuntimeError: dictionary changed size during
		iteration`` and the request fails with HTTP 500. The tuple is the fix, not the
		lock alone.
		"""
		with self._cls_lock:
			return tuple(self._dict_items.values())
