# DDD Service — Bank Balance Alert Example

A complete illustrative example showing how to structure a banking feature with balance alerts using DDD hexagonal architecture.

> **See also:** [Core concepts](../ddd-service.md) · [Usage examples](ddd-usage-examples.md) · [External API calls](ddd-external-api.md)

---

## Overview

This example demonstrates:
- Multiple ports (repository + notification)
- Domain entities with business meaning
- Use-case orchestrating multiple collaborators
- Infrastructure adapters for persistence and notifications

**Not scaffolded** — illustrative only.

---

## Domain Layer

### Entities

**`modules/banking/domain/entities.py`**
```python
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Account:
    id: str
    owner_email: str
    balance: float
    updated_at: datetime
```

### Ports

**`modules/banking/domain/ports.py`**
```python
from typing import Protocol
from .entities import Account


class AccountRepository(Protocol):
    """Port for account persistence."""

    def get(self, account_id: str) -> Account | None:
        """Retrieve an account by ID."""
        ...

    def save(self, account: Account) -> None:
        """Persist an account."""
        ...


class NotificationPort(Protocol):
    """Port for sending notifications."""

    def send_balance_alert(
        self,
        to_email: str,
        current_balance: float,
        threshold: float,
    ) -> None:
        """Send a low-balance alert to the account owner."""
        ...
```

---

## Application Layer

**`modules/banking/application/balance_alert.py`**
```python
from ..domain.entities import Account
from ..domain.ports import AccountRepository, NotificationPort


class BalanceAlertService:
    """Use-case: check account balance and send alert if below threshold."""

    def __init__(self, accounts: AccountRepository, notifier: NotificationPort):
        self.accounts = accounts
        self.notifier = notifier

    def execute(self, account_id: str, threshold: float) -> bool:
        """
        Check if account balance is below threshold and send alert.
        
        Returns:
            True if alert was sent, False otherwise.
        """
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
```

---

## Infrastructure Layer

### Repository Adapter

**`modules/banking/infrastructure/repositories.py`**
```python
from ..domain.entities import Account
from ..domain.ports import AccountRepository


class InMemoryAccountRepository(AccountRepository):
    """In-memory implementation for testing and demos."""

    def __init__(self):
        self.items: dict[str, Account] = {}

    def get(self, account_id: str) -> Account | None:
        return self.items.get(account_id)

    def save(self, account: Account) -> None:
        self.items[account.id] = account
```

### Notification Adapter

**`modules/banking/infrastructure/notifications.py`**
```python
from ..domain.ports import NotificationPort


class EmailNotificationAdapter(NotificationPort):
    """Email notification adapter (console output for demo)."""

    def send_balance_alert(
        self,
        to_email: str,
        current_balance: float,
        threshold: float,
    ) -> None:
        print(
            f"📧 Email -> {to_email}: "
            f"Your balance (${current_balance:.2f}) is below ${threshold:.2f}"
        )


class SlackNotificationAdapter(NotificationPort):
    """Alternative: Slack notification adapter."""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send_balance_alert(
        self,
        to_email: str,
        current_balance: float,
        threshold: float,
    ) -> None:
        import requests
        requests.post(self.webhook_url, json={
            "text": f"⚠️ Low balance alert for {to_email}: ${current_balance:.2f} < ${threshold:.2f}"
        })
```

---

## Wiring & Running

**`modules/banking/main.py`**
```python
from datetime import datetime
from .application.balance_alert import BalanceAlertService
from .infrastructure.notifications import EmailNotificationAdapter
from .infrastructure.repositories import InMemoryAccountRepository
from .domain.entities import Account


def run_demo() -> None:
    # Wire dependencies
    accounts = InMemoryAccountRepository()
    notifier = EmailNotificationAdapter()
    service = BalanceAlertService(accounts, notifier)

    # Seed data
    accounts.save(Account(
        id="acc-123",
        owner_email="user@example.com",
        balance=49.0,
        updated_at=datetime.utcnow(),
    ))

    # Execute use-case
    alert_sent = service.execute(account_id="acc-123", threshold=50.0)
    print(f"Alert sent: {alert_sent}")


if __name__ == "__main__":
    run_demo()
```

**Output:**
```
📧 Email -> user@example.com: Your balance ($49.00) is below $50.00
Alert sent: True
```

---

## Testing

```python
import pytest
from unittest.mock import Mock
from datetime import datetime
from modules.banking.application.balance_alert import BalanceAlertService
from modules.banking.domain.entities import Account


class TestBalanceAlertService:
    def test_sends_alert_when_below_threshold(self):
        mock_repo = Mock()
        mock_repo.get.return_value = Account(
            id="acc-1",
            owner_email="test@example.com",
            balance=40.0,
            updated_at=datetime.utcnow(),
        )
        mock_notifier = Mock()

        service = BalanceAlertService(mock_repo, mock_notifier)
        result = service.execute("acc-1", threshold=50.0)

        assert result is True
        mock_notifier.send_balance_alert.assert_called_once_with(
            to_email="test@example.com",
            current_balance=40.0,
            threshold=50.0,
        )

    def test_no_alert_when_above_threshold(self):
        mock_repo = Mock()
        mock_repo.get.return_value = Account(
            id="acc-1",
            owner_email="test@example.com",
            balance=100.0,
            updated_at=datetime.utcnow(),
        )
        mock_notifier = Mock()

        service = BalanceAlertService(mock_repo, mock_notifier)
        result = service.execute("acc-1", threshold=50.0)

        assert result is False
        mock_notifier.send_balance_alert.assert_not_called()

    def test_no_alert_when_account_not_found(self):
        mock_repo = Mock()
        mock_repo.get.return_value = None
        mock_notifier = Mock()

        service = BalanceAlertService(mock_repo, mock_notifier)
        result = service.execute("nonexistent", threshold=50.0)

        assert result is False
        mock_notifier.send_balance_alert.assert_not_called()
```

---

## Key Takeaways

| Aspect | Implementation |
|--------|---------------|
| **Multiple ports** | `AccountRepository` + `NotificationPort` — domain defines what it needs |
| **Single responsibility** | Each adapter does one thing (persist or notify) |
| **Testability** | Mock both ports independently |
| **Extensibility** | Add `SlackNotificationAdapter` without changing domain or use-case |
