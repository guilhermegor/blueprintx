"""HTTP transport adapter (inbound port) for the example_feature capability.

Translates HTTP requests into calls against pre-wired callables — the composition root
(src/app/api.py) injects the exact functions this router needs, never the container itself,
so this layer never imports app/ (the same direction infrastructure/ already enforces for
the outbound side).
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, status

from capabilities.example_feature.domain.dto import NoteCreateDTO, NoteResponseDTO


def build_example_feature_router(
	fn_create_note: Callable[[NoteCreateDTO], NoteResponseDTO],
	fn_list_notes: Callable[[], list[NoteResponseDTO]],
) -> APIRouter:
	"""Build the example_feature router, bound to injected application callables.

	Parameters
	----------
	fn_create_note : Callable[[NoteCreateDTO], NoteResponseDTO]
		Application entry point that creates and persists a note.
	fn_list_notes : Callable[[], list[NoteResponseDTO]]
		Application entry point that lists all notes.

	Returns
	-------
	APIRouter
		Router exposing the note endpoints, ready to `include_router` into the app.
	"""
	cls_router = APIRouter(prefix="/notes", tags=["notes"])

	@cls_router.post("", response_model=NoteResponseDTO, status_code=status.HTTP_201_CREATED)
	def create_note(cls_dto: NoteCreateDTO) -> NoteResponseDTO:
		"""Create a note from the request body and return the stored representation."""
		return fn_create_note(cls_dto)

	@cls_router.get("", response_model=list[NoteResponseDTO])
	def list_notes() -> list[NoteResponseDTO]:
		"""Return every stored note."""
		return fn_list_notes()

	return cls_router
