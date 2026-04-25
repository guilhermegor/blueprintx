"""Composition root: instantiates infrastructure and wires application entry points."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from capabilities.example_feature.application import create_note, list_notes
from capabilities.example_feature.domain.dto import NoteCreateDTO, NoteResponseDTO
from capabilities.example_feature.infrastructure.repositories import InMemoryNoteRepository
from chassis.db_schema.application import build_database_handler


@dataclass(frozen=True)
class AppContainer:
	"""Holds pre-wired application entry points ready for use by main.

	Attributes
	----------
	create_note : Callable[[NoteCreateDTO], NoteResponseDTO]
		Create and persist a note from an inbound DTO.
	list_notes : Callable[[], list[NoteResponseDTO]]
		Retrieve all notes as response DTOs.
	"""

	create_note: Callable[[NoteCreateDTO], NoteResponseDTO]
	list_notes: Callable[[], list[NoteResponseDTO]]


def build() -> AppContainer:
	"""Instantiate infrastructure and bind it to application factories.

	Returns
	-------
	AppContainer
		Fully wired container ready for use.

	Notes
	-----
	Replace ``InMemoryNoteRepository`` with a ``DatabaseSession``-backed
	implementation once a persistent store is configured.
	"""
	cls_db_handler = build_database_handler()
	cls_note_repo = InMemoryNoteRepository()
	return AppContainer(
		create_note=lambda cls_dto: create_note(cls_dto, cls_note_repo),
		list_notes=lambda: list_notes(cls_note_repo),
	)
