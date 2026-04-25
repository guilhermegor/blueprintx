"""Domain enums for the example_feature capability."""

from enum import Enum


class NoteStatus(Enum):
	DRAFT = "draft"
	PUBLISHED = "published"
	ARCHIVED = "archived"
