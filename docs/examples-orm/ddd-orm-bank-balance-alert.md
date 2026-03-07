# **DDD Service (ORM) — Bank Balance Alert Example**

A complete illustrative example showing how to structure a banking feature with balance alerts using DDD hexagonal architecture and SQLAlchemy ORM.

> **See also:** [Core concepts](../ddd-service-orm-db.md) · [Usage examples](ddd-orm-usage-examples.md) · [External API calls](ddd-orm-external-api.md)

---

## Overview

This example demonstrates:
- Multiple ports (repository + notification)
- SQLAlchemy models with relationships
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
from typing import Optional


@dataclass
class Account:
    id: str
    owner_email: str
    balance: float
    updated_at: datetime
    owner_name: Optional[str] = None


@dataclass
class AlertLog:
    """Record of sent alerts for auditing."""
    id: str
    account_id: str
    threshold: float
    balance_at_alert: float
    sent_at: datetime
```

### Ports

**`modules/banking/domain/ports.py`**
```python
from typing import Protocol, Optional
from datetime import datetime
from .entities import Account, AlertLog


class AccountRepository(Protocol):
    """Port for account persistence."""

    def get(self, account_id: str) -> Optional[Account]:
        """Retrieve an account by ID."""
        ...

    def save(self, account: Account) -> Account:
        """Persist an account."""
        ...

    def get_below_threshold(self, threshold: float) -> list[Account]:
        """Get all accounts with balance below threshold."""
        ...


class AlertLogRepository(Protocol):
    """Port for alert log persistence."""

    def save(self, alert: AlertLog) -> AlertLog:
        """Persist an alert log entry."""
        ...

    def get_recent_for_account(
        self, account_id: str, since: datetime
    ) -> list[AlertLog]:
        """Get recent alerts for an account."""
        ...


class NotificationPort(Protocol):
    """Port for sending notifications."""

    def send_balance_alert(
        self,
        to_email: str,
        owner_name: str,
        current_balance: float,
        threshold: float,
    ) -> bool:
        """Send a low-balance alert. Returns True if sent successfully."""
        ...
```

---

## Infrastructure Layer — SQLAlchemy Models

**`modules/banking/infrastructure/models.py`**
```python
from datetime import datetime
from sqlalchemy import String, Float, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from core.infrastructure.database import Base, generate_uuid


class AccountModel(Base):
    """SQLAlchemy model for bank accounts."""

    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    owner_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    owner_name: Mapped[str] = mapped_column(String(255), nullable=True)
    balance: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationship to alert logs
    alerts: Mapped[list["AlertLogModel"]] = relationship(
        "AlertLogModel", back_populates="account", cascade="all, delete-orphan"
    )

    def to_entity(self) -> "Account":
        from ..domain.entities import Account
        return Account(
            id=self.id,
            owner_email=self.owner_email,
            owner_name=self.owner_name,
            balance=self.balance,
            updated_at=self.updated_at,
        )

    @classmethod
    def from_entity(cls, entity: "Account") -> "AccountModel":
        return cls(
            id=entity.id,
            owner_email=entity.owner_email,
            owner_name=entity.owner_name,
            balance=entity.balance,
            updated_at=entity.updated_at,
        )


class AlertLogModel(Base):
    """SQLAlchemy model for alert audit logs."""

    __tablename__ = "alert_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("accounts.id"), nullable=False, index=True
    )
    threshold: Mapped[float] = mapped_column(Float, nullable=False)
    balance_at_alert: Mapped[float] = mapped_column(Float, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationship back to account
    account: Mapped["AccountModel"] = relationship("AccountModel", back_populates="alerts")

    def to_entity(self) -> "AlertLog":
        from ..domain.entities import AlertLog
        return AlertLog(
            id=self.id,
            account_id=self.account_id,
            threshold=self.threshold,
            balance_at_alert=self.balance_at_alert,
            sent_at=self.sent_at,
        )
```

---

## Infrastructure Layer — Repositories

**`modules/banking/infrastructure/repositories.py`**
```python
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from core.infrastructure.database import Repository, generate_uuid
from .models import AccountModel, AlertLogModel
from ..domain.entities import Account, AlertLog
from ..domain.ports import AccountRepository, AlertLogRepository


class SQLAlchemyAccountRepository(AccountRepository, Repository):
    """SQLAlchemy implementation of AccountRepository."""

    def __init__(self, session: Session):
        super().__init__(session)

    def get(self, account_id: str) -> Optional[Account]:
        model = self.session.get(AccountModel, account_id)
        return model.to_entity() if model else None

    def save(self, account: Account) -> Account:
        model = self.session.get(AccountModel, account.id)
        if model:
            # Update existing
            model.owner_email = account.owner_email
            model.owner_name = account.owner_name
            model.balance = account.balance
        else:
            # Create new
            model = AccountModel.from_entity(account)
            self.session.add(model)
        self.session.flush()
        return account

    def get_below_threshold(self, threshold: float) -> list[Account]:
        stmt = select(AccountModel).where(AccountModel.balance < threshold)
        models = self.session.execute(stmt).scalars().all()
        return [m.to_entity() for m in models]


class SQLAlchemyAlertLogRepository(AlertLogRepository, Repository):
    """SQLAlchemy implementation of AlertLogRepository."""

    def __init__(self, session: Session):
        super().__init__(session)

    def save(self, alert: AlertLog) -> AlertLog:
        model = AlertLogModel(
            id=alert.id or generate_uuid(),
            account_id=alert.account_id,
            threshold=alert.threshold,
            balance_at_alert=alert.balance_at_alert,
            sent_at=alert.sent_at,
        )
        self.session.add(model)
        self.session.flush()
        alert.id = model.id
        return alert

    def get_recent_for_account(
        self, account_id: str, since: datetime
    ) -> list[AlertLog]:
        stmt = (
            select(AlertLogModel)
            .where(AlertLogModel.account_id == account_id)
            .where(AlertLogModel.sent_at >= since)
            .order_by(AlertLogModel.sent_at.desc())
        )
        models = self.session.execute(stmt).scalars().all()
        return [m.to_entity() for m in models]
```

---

## Infrastructure Layer — Notification Adapters

**`modules/banking/infrastructure/notifications.py`**
```python
from ..domain.ports import NotificationPort


class EmailNotificationAdapter(NotificationPort):
    """Email notification adapter (console output for demo)."""

    def send_balance_alert(
        self,
        to_email: str,
        owner_name: str,
        current_balance: float,
        threshold: float,
    ) -> bool:
        name = owner_name or "Customer"
        print(
            f"📧 Email -> {to_email}: "
            f"Hi {name}, your balance (${current_balance:.2f}) is below ${threshold:.2f}"
        )
        return True


class SlackNotificationAdapter(NotificationPort):
    """Alternative: Slack notification adapter."""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url

    def send_balance_alert(
        self,
        to_email: str,
        owner_name: str,
        current_balance: float,
        threshold: float,
    ) -> bool:
        import requests
        response = requests.post(self.webhook_url, json={
            "text": f"⚠️ Low balance alert for {owner_name} ({to_email}): ${current_balance:.2f} < ${threshold:.2f}"
        })
        return response.status_code == 200
```

---

## Application Layer

**`modules/banking/application/balance_alert.py`**
```python
from datetime import datetime, timedelta
from ..domain.entities import AlertLog
from ..domain.ports import AccountRepository, AlertLogRepository, NotificationPort
from core.infrastructure.database import generate_uuid


class BalanceAlertService:
    """Use-case: check account balance and send alert if below threshold."""

    def __init__(
        self,
        accounts: AccountRepository,
        alert_logs: AlertLogRepository,
        notifier: NotificationPort,
        cooldown_hours: int = 24,
    ):
        self.accounts = accounts
        self.alert_logs = alert_logs
        self.notifier = notifier
        self.cooldown_hours = cooldown_hours

    def execute(self, account_id: str, threshold: float) -> bool:
        """
        Check if account balance is below threshold and send alert.
        
        Respects cooldown period to avoid spamming.
        
        Returns:
            True if alert was sent, False otherwise.
        """
        account = self.accounts.get(account_id)
        if account is None:
            return False
        
        if account.balance >= threshold:
            return False
        
        # Check cooldown
        since = datetime.utcnow() - timedelta(hours=self.cooldown_hours)
        recent_alerts = self.alert_logs.get_recent_for_account(account_id, since)
        if recent_alerts:
            return False  # Already alerted recently
        
        # Send notification
        success = self.notifier.send_balance_alert(
            to_email=account.owner_email,
            owner_name=account.owner_name or "Customer",
            current_balance=account.balance,
            threshold=threshold,
        )
        
        if success:
            # Log the alert
            alert_log = AlertLog(
                id=generate_uuid(),
                account_id=account_id,
                threshold=threshold,
                balance_at_alert=account.balance,
                sent_at=datetime.utcnow(),
            )
            self.alert_logs.save(alert_log)
        
        return success


class BulkBalanceAlertService:
    """Use-case: check all accounts and send alerts for those below threshold."""

    def __init__(
        self,
        accounts: AccountRepository,
        alert_logs: AlertLogRepository,
        notifier: NotificationPort,
        cooldown_hours: int = 24,
    ):
        self.single_alert = BalanceAlertService(
            accounts, alert_logs, notifier, cooldown_hours
        )
        self.accounts = accounts

    def execute(self, threshold: float) -> int:
        """
        Check all accounts below threshold and send alerts.
        
        Returns:
            Number of alerts sent.
        """
        low_balance_accounts = self.accounts.get_below_threshold(threshold)
        alerts_sent = 0
        
        for account in low_balance_accounts:
            if self.single_alert.execute(account.id, threshold):
                alerts_sent += 1
        
        return alerts_sent
```

---

## Wiring & Running

**`modules/banking/main.py`**
```python
from datetime import datetime
from core.application import build_database_session
from core.infrastructure.database import generate_uuid
from .application.balance_alert import BalanceAlertService, BulkBalanceAlertService
from .infrastructure.notifications import EmailNotificationAdapter
from .infrastructure.repositories import (
    SQLAlchemyAccountRepository,
    SQLAlchemyAlertLogRepository,
)
from .domain.entities import Account


def run_demo() -> None:
    # Setup database
    db = build_database_session()
    db.create_tables()
    
    with db.session() as session:
        # Wire dependencies
        accounts = SQLAlchemyAccountRepository(session)
        alert_logs = SQLAlchemyAlertLogRepository(session)
        notifier = EmailNotificationAdapter()
        
        # Create services
        single_alert = BalanceAlertService(accounts, alert_logs, notifier)
        bulk_alert = BulkBalanceAlertService(accounts, alert_logs, notifier)

        # Seed data
        accounts.save(Account(
            id=generate_uuid(),
            owner_email="alice@example.com",
            owner_name="Alice",
            balance=49.0,
            updated_at=datetime.utcnow(),
        ))
        accounts.save(Account(
            id=generate_uuid(),
            owner_email="bob@example.com",
            owner_name="Bob",
            balance=150.0,
            updated_at=datetime.utcnow(),
        ))
        accounts.save(Account(
            id=generate_uuid(),
            owner_email="carol@example.com",
            owner_name="Carol",
            balance=25.0,
            updated_at=datetime.utcnow(),
        ))
        session.commit()

        # Execute bulk alerts
        print("\n--- Running bulk alerts (threshold: $50) ---")
        alerts_sent = bulk_alert.execute(threshold=50.0)
        session.commit()
        print(f"\nTotal alerts sent: {alerts_sent}")


if __name__ == "__main__":
    run_demo()
```

**Output:**
```
--- Running bulk alerts (threshold: $50) ---
📧 Email -> alice@example.com: Hi Alice, your balance ($49.00) is below $50.00
📧 Email -> carol@example.com: Hi Carol, your balance ($25.00) is below $50.00

Total alerts sent: 2
```

---

## Testing

```python
import pytest
from unittest.mock import Mock
from datetime import datetime, timedelta
from core.infrastructure.database import DatabaseSession, generate_uuid
from modules.banking.infrastructure.repositories import (
    SQLAlchemyAccountRepository,
    SQLAlchemyAlertLogRepository,
)
from modules.banking.application.balance_alert import BalanceAlertService
from modules.banking.domain.entities import Account, AlertLog


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing."""
    db = DatabaseSession("sqlite:///:memory:")
    db.create_tables()
    with db.session() as session:
        yield session


class TestBalanceAlertService:
    def test_sends_alert_when_below_threshold(self, db_session):
        accounts = SQLAlchemyAccountRepository(db_session)
        alert_logs = SQLAlchemyAlertLogRepository(db_session)
        mock_notifier = Mock()
        mock_notifier.send_balance_alert.return_value = True

        # Create account
        account = Account(
            id=generate_uuid(),
            owner_email="test@example.com",
            owner_name="Test User",
            balance=40.0,
            updated_at=datetime.utcnow(),
        )
        accounts.save(account)
        db_session.commit()

        service = BalanceAlertService(accounts, alert_logs, mock_notifier)
        result = service.execute(account.id, threshold=50.0)
        db_session.commit()

        assert result is True
        mock_notifier.send_balance_alert.assert_called_once_with(
            to_email="test@example.com",
            owner_name="Test User",
            current_balance=40.0,
            threshold=50.0,
        )

    def test_no_alert_when_above_threshold(self, db_session):
        accounts = SQLAlchemyAccountRepository(db_session)
        alert_logs = SQLAlchemyAlertLogRepository(db_session)
        mock_notifier = Mock()

        account = Account(
            id=generate_uuid(),
            owner_email="test@example.com",
            owner_name="Test",
            balance=100.0,
            updated_at=datetime.utcnow(),
        )
        accounts.save(account)
        db_session.commit()

        service = BalanceAlertService(accounts, alert_logs, mock_notifier)
        result = service.execute(account.id, threshold=50.0)

        assert result is False
        mock_notifier.send_balance_alert.assert_not_called()

    def test_respects_cooldown_period(self, db_session):
        accounts = SQLAlchemyAccountRepository(db_session)
        alert_logs = SQLAlchemyAlertLogRepository(db_session)
        mock_notifier = Mock()
        mock_notifier.send_balance_alert.return_value = True

        account = Account(
            id=generate_uuid(),
            owner_email="test@example.com",
            owner_name="Test",
            balance=40.0,
            updated_at=datetime.utcnow(),
        )
        accounts.save(account)
        db_session.commit()

        service = BalanceAlertService(accounts, alert_logs, mock_notifier, cooldown_hours=24)
        
        # First alert should succeed
        result1 = service.execute(account.id, threshold=50.0)
        db_session.commit()
        assert result1 is True
        
        # Second alert should be blocked by cooldown
        result2 = service.execute(account.id, threshold=50.0)
        assert result2 is False
        
        # Notifier called only once
        assert mock_notifier.send_balance_alert.call_count == 1

    def test_no_alert_when_account_not_found(self, db_session):
        accounts = SQLAlchemyAccountRepository(db_session)
        alert_logs = SQLAlchemyAlertLogRepository(db_session)
        mock_notifier = Mock()

        service = BalanceAlertService(accounts, alert_logs, mock_notifier)
        result = service.execute("nonexistent-id", threshold=50.0)

        assert result is False
        mock_notifier.send_balance_alert.assert_not_called()
```

---

## Key Takeaways

| Aspect | Implementation |
|--------|---------------|
| **ORM Models** | `AccountModel` and `AlertLogModel` with SQLAlchemy relationships |
| **Multiple ports** | `AccountRepository` + `AlertLogRepository` + `NotificationPort` |
| **Audit trail** | Alert logs persisted for compliance and debugging |
| **Cooldown** | Prevents spamming users with repeated alerts |
| **Bulk operations** | `BulkBalanceAlertService` for batch processing |
| **Testability** | In-memory SQLite + mocked notifier for fast tests |
