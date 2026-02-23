from __future__ import annotations

from typing import Protocol

from .entities import Account


class AccountRepository(Protocol):
    def get(self, account_id: str) -> Account | None: ...
    def save(self, account: Account) -> None: ...


class NotificationPort(Protocol):
    def send_balance_alert(self, to_email: str, current_balance: float, threshold: float) -> None: ...
