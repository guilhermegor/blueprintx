"""Domain entities for the example feature."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Note:
    """Simple note entity owned by this feature's domain."""

    id: str
    title: str
    created_at: datetime
