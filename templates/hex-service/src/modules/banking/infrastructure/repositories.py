from __future__ import annotations

from ..domain.entities import Account
from ..domain.ports import AccountRepository


class InMemoryAccountRepository(AccountRepository):
    def __init__(self):
        self.items: dict[str, Account] = {}

    def get(self, account_id: str) -> Account | None:
        return self.items.get(account_id)

    def save(self, account: Account) -> None:
        self.items[account.id] = account
