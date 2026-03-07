"""Application use-cases orchestrating the example feature's domain and ports."""

from __future__ import annotations

from datetime import datetime
import uuid

from ..domain.entities import Note
from ..domain.ports import NoteRepository


class CreateNote:
    """Create a new note using the repository port."""

    def __init__(self, repo: NoteRepository):
        self.repo = repo

    def execute(self, title: str) -> Note:
        note = Note(id=uuid.uuid4().hex, title=title, created_at=datetime.utcnow())
        return self.repo.add(note)


class ListNotes:
    """List all notes from the repository."""

    def __init__(self, repo: NoteRepository):
        self.repo = repo

    def execute(self):
        return list(self.repo.list())
