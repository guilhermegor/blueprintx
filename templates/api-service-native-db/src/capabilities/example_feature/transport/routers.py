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
from chassis.typing import TypeChecker


class _ExampleFeatureEndpoints(metaclass=TypeChecker):
	"""Route handlers bound to injected application callables.

	A class here satisfies the DI trigger (common.md "Class vs function"): each method needs
	the callable handed to `build_example_feature_router` at construction time. Two named
	methods, rather than two nested `def`s inside the builder, are also what keeps that
	builder's cyclomatic complexity at the tier's `src/` ceiling of 2 — mccabe counts a nested
	function definition as a branch of its enclosing scope.
	"""

	def __init__(
		self,
		fn_create_note: Callable[[NoteCreateDTO], NoteResponseDTO],
		fn_list_notes: Callable[[], list[NoteResponseDTO]],
	) -> None:
		self._fn_create_note = fn_create_note
		self._fn_list_notes = fn_list_notes

	def create_note(self, cls_dto: NoteCreateDTO) -> NoteResponseDTO:
		"""Create a note from the request body and return the stored representation."""
		return self._fn_create_note(cls_dto)

	def list_notes(self) -> list[NoteResponseDTO]:
		"""Return every stored note."""
		return self._fn_list_notes()


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
	cls_endpoints = _ExampleFeatureEndpoints(fn_create_note, fn_list_notes)
	cls_router = APIRouter(prefix="/notes", tags=["notes"])
	cls_router.add_api_route(
		"",
		cls_endpoints.create_note,
		methods=["POST"],
		response_model=NoteResponseDTO,
		status_code=status.HTTP_201_CREATED,
	)
	cls_router.add_api_route(
		"",
		cls_endpoints.list_notes,
		methods=["GET"],
		response_model=list[NoteResponseDTO],
	)
	return cls_router
