"""Ports (structural interfaces) the domain expects infrastructure to implement."""

from __future__ import annotations

from typing import Iterable, Protocol

from .entities import Note


class NoteRepository(Protocol):
	"""Repository port for persisting notes.

	Any class that implements add / get / list satisfies this port —
	no inheritance required.
	"""

	def add(self, cls_note: Note) -> Note: ...
	def get(self, str_note_id: str) -> Note | None: ...
	def list(self) -> Iterable[Note]: ...
