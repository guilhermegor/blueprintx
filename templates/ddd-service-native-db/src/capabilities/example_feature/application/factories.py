"""Application service layer for the example_feature capability.

Bridges the transport boundary (DTOs) and the domain (entities + use-cases).
No infrastructure imports — the repo is injected by the caller.
"""

from __future__ import annotations

from ..domain.dto import NoteCreateDTO, NoteResponseDTO
from ..domain.entities import Note
from ..domain.ports import NoteRepository
from .use_cases import CreateNote, ListNotes


# --- assemblers (DTO ↔ entity) ---


def note_from_create_dto(cls_dto: NoteCreateDTO) -> Note:
	"""Build a Note entity from an inbound create payload.

	Parameters
	----------
	cls_dto : NoteCreateDTO
		Inbound network payload.

	Returns
	-------
	Note
		Domain entity with system-assigned id, created_at, and status defaults.
	"""
	return Note(title=cls_dto.title)


def note_to_response_dto(cls_note: Note) -> NoteResponseDTO:
	"""Serialize a Note entity into an outbound response payload.

	Parameters
	----------
	cls_note : Note
		Persisted domain entity.

	Returns
	-------
	NoteResponseDTO
		Network-safe response shape.
	"""
	return NoteResponseDTO(
		id=cls_note.id,
		title=cls_note.title,
		created_at=cls_note.created_at,
		status=cls_note.status,
	)


# --- application service entry points ---


def create_note(cls_dto: NoteCreateDTO, cls_repo: NoteRepository) -> NoteResponseDTO:
	"""Translate DTO → entity, persist via use-case, return response DTO.

	Parameters
	----------
	cls_dto : NoteCreateDTO
		Inbound create payload.
	cls_repo : NoteRepository
		Repository port implementation (injected by the caller).

	Returns
	-------
	NoteResponseDTO
		Response payload for the newly created note.
	"""
	cls_note = note_from_create_dto(cls_dto)
	cls_saved = CreateNote(cls_repo).execute(cls_note)
	return note_to_response_dto(cls_saved)


def list_notes(cls_repo: NoteRepository) -> list[NoteResponseDTO]:
	"""Retrieve all notes and return them as response DTOs.

	Parameters
	----------
	cls_repo : NoteRepository
		Repository port implementation (injected by the caller).

	Returns
	-------
	list[NoteResponseDTO]
		All stored notes as response payloads.
	"""
	list_items = ListNotes(cls_repo).execute()
	return [note_to_response_dto(cls_n) for cls_n in list_items]
