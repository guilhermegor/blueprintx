"""ASGI application factory: wires the composition root into HTTP transport."""

from __future__ import annotations

from fastapi import FastAPI

from app.container import build
from capabilities.example_feature.transport import build_example_feature_router
from chassis.typing import type_checker


@type_checker
def create_app() -> FastAPI:
	"""Build the FastAPI app with every capability's router mounted.

	Returns
	-------
	FastAPI
		Application ready to serve, wired to a freshly built :class:`AppContainer`.
	"""
	cls_container = build()
	cls_app = FastAPI(title="API Service", version="0.0.1")
	cls_app.include_router(
		build_example_feature_router(cls_container.create_note, cls_container.list_notes)
	)

	@cls_app.get("/health", tags=["health"])
	def health() -> dict[str, str]:
		"""Liveness probe — no dependencies, always returns ok once the process is up."""
		return {"status": "ok"}

	return cls_app
