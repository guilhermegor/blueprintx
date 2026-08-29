"""Domain layer for the shared database contract."""

from .ports import DatabaseHandler, Record


__all__ = ["DatabaseHandler", "Record"]
