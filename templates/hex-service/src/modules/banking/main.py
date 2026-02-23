from __future__ import annotations

from datetime import datetime

from .application.balance_alert import BalanceAlertService
from .domain.entities import Account
from .infrastructure.notifications import EmailNotificationAdapter
from .infrastructure.repositories import InMemoryAccountRepository


def run_demo() -> None:
    accounts = InMemoryAccountRepository()
    notifier = EmailNotificationAdapter()
    service = BalanceAlertService(accounts, notifier)

    accounts.save(
        Account(
            id="acc-123",
            owner_email="user@example.com",
            balance=49.0,
            updated_at=datetime.utcnow(),
        )
    )
    service.execute(account_id="acc-123", threshold=50.0)


if __name__ == "__main__":
    run_demo()
