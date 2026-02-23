from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Account:
    id: str
    owner_email: str
    balance: float
    updated_at: datetime
