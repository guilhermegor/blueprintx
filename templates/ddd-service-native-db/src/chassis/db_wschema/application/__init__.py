"""Application layer for schema-less storage backends."""

from .storage_factory import build_storage_handler


__all__ = ["build_storage_handler"]
