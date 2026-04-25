"""Domain layer for the example_feature capability.

- entities.py  persistence shape (maps to a DB row)
- dto.py       network shape (API input / output)
- enums.py     shared domain types
- ports.py     repository interfaces (Protocols)
"""

from .dto import NoteCreateDTO, NoteResponseDTO
from .entities import Note
from .enums import NoteStatus
from .ports import NoteRepository

__all__ = ["Note", "NoteCreateDTO", "NoteResponseDTO", "NoteStatus", "NoteRepository"]
