from __future__ import annotations

from ..domain.entities import Account
from ..domain.ports import AccountRepository, NotificationPort


class BalanceAlertService:
    def __init__(self, accounts: AccountRepository, notifier: NotificationPort):
        self.accounts = accounts
        self.notifier = notifier

    def execute(self, account_id: str, threshold: float) -> bool:
        account = self.accounts.get(account_id)
        if account is None:
            return False
        if account.balance < threshold:
            self.notifier.send_balance_alert(
                to_email=account.owner_email,
                current_balance=account.balance,
                threshold=threshold,
            )
            return True
        return False
