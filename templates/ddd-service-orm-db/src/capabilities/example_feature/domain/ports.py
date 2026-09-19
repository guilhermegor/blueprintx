"""Ports (structural interfaces) the domain expects infrastructure to implement."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from chassis.typing import ProtocolTypeCheckerMeta

from .entities import Note


class NoteRepository(Protocol, metaclass=ProtocolTypeCheckerMeta):
    """Repository port for persisting notes.

    Any class that implements add / get / list satisfies this port —
    no inheritance required.
    """

    def add(self, cls_note: Note) -> Note:
        """Persist a note and return the stored entity."""
        ...

    def get(self, str_note_id: str) -> Note | None:
        """Fetch a note by id, or None when it does not exist."""
        ...

    def list(self) -> Iterable[Note]:
        """Return every stored note."""
        ...
