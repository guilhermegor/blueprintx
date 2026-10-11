"""Domain enums for the example_feature capability."""

from enum import Enum


class NoteStatus(Enum):
    """Lifecycle status of a Note."""

    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"
