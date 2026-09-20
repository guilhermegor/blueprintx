"""Network-layer DTOs for the example_feature capability."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .enums import NoteStatus


@dataclass
class NoteCreateDTO:
	"""Inbound payload for creating a note (id assigned by the system)."""

	title: str


@dataclass
class NoteResponseDTO:
	"""Outbound payload returned over the network."""

	id: str
	title: str
	created_at: datetime
	status: NoteStatus
