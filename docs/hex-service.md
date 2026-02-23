# Hex Service (hex/DDD-flavored Python)

A pragmatic, per-feature layout that keeps business logic isolated from I/O while allowing shared infrastructure when it is truly cross-cutting.

## Expected layout (after scaffold)
```
project/
  src/
    core/{domain,infrastructure,application}
    modules/<feature>/{domain,application,infrastructure}
    utils/
    config/
    main.py
  tests/{unit,integration,performance}/
  container/
    scripts/
  data/
  docs/
  public/
  .github/workflows/
  .vscode/
  .env
  pyproject.toml
```

## Domain (core/domain or modules/<feature>/domain)
What goes here: Entities, value objects, domain services (pure business logic), and the ports (interfaces) the domain needs. No framework or I/O.

Example entity: [templates/hex-service/src/modules/example_feature/domain/entities.py](https://github.com/guilhermegor/BlueprintX/blob/main/templates/hex-service/src/modules/example_feature/domain/entities.py#L1-L15)
```python
from dataclasses import dataclass
from datetime import datetime

@dataclass
class Note:
    id: str
    title: str
    created_at: datetime
```

Example port: [templates/hex-service/src/modules/example_feature/domain/ports.py](https://github.com/guilhermegor/BlueprintX/blob/main/templates/hex-service/src/modules/example_feature/domain/ports.py#L1-L24)
```python
from abc import ABC, abstractmethod
from typing import Iterable
from .entities import Note

class NoteRepository(ABC):
    @abstractmethod
    def add(self, note: Note) -> Note: ...
    @abstractmethod
    def get(self, note_id: str) -> Note | None: ...
    @abstractmethod
    def list(self) -> Iterable[Note]: ...
```

## Application (core/application or modules/<feature>/application)
What goes here: Use-case orchestration; coordinates domain objects and ports. Enforces transaction boundaries and policies; still framework-free.

Example use-case: [templates/hex-service/src/modules/example_feature/application/use_cases.py](https://github.com/guilhermegor/BlueprintX/blob/main/templates/hex-service/src/modules/example_feature/application/use_cases.py#L1-L30)
```python
from datetime import datetime
import uuid
from ..domain.entities import Note
from ..domain.ports import NoteRepository

class CreateNote:
    def __init__(self, repo: NoteRepository):
        self.repo = repo

    def execute(self, title: str) -> Note:
        note = Note(id=uuid.uuid4().hex, title=title, created_at=datetime.utcnow())
        return self.repo.add(note)
```

## Infrastructure (core/infrastructure or modules/<feature>/infrastructure)
What goes here: Adapters implementing ports (DB, HTTP clients, brokers), configuration glue, persistence mappers. Keep side effects here.

Example adapter implementing the repository port: [templates/hex-service/src/modules/example_feature/infrastructure/repositories.py](https://github.com/guilhermegor/BlueprintX/blob/main/templates/hex-service/src/modules/example_feature/infrastructure/repositories.py#L1-L25)
```python
from ..domain.entities import Note
from ..domain.ports import NoteRepository

class InMemoryNoteRepository(NoteRepository):
    def __init__(self):
        self._items: dict[str, Note] = {}

    def add(self, note: Note) -> Note:
        self._items[note.id] = note
        return note
```

Shared database backends live under `core/infrastructure/database/`, with runtime selection handled in [templates/hex-service/src/main.py](https://github.com/guilhermegor/BlueprintX/blob/main/templates/hex-service/src/main.py#L22-L133) using `DB_BACKEND` (json, csv, sqlite, postgresql, mariadb, mysql).

## Modules (modules/<feature>)
What goes here: Feature/bounded-context composition—wire domain + app + infra for that feature. Also entrypoints like API/CLI handlers.

Example wiring and handler sketch:
```python
# composition
repo = InMemoryNoteRepository()
create_note = CreateNote(repo)
list_notes = ListNotes(repo)

# API handler (FastAPI-style example)
from fastapi import APIRouter
router = APIRouter()

@router.post("/notes")
def create_note_endpoint(payload: CreateNotePayload):
    note = create_note.execute(title=payload.title)
    return {"id": note.id, "title": note.title, "created_at": note.created_at.isoformat()}
```

## Rules of thumb
- Domain: pure logic and contracts; no I/O or frameworks.
- Application: orchestrate use-cases, transactions, and policies; still framework-free.
- Infrastructure: all I/O adapters implementing ports (DB, HTTP, queues, files).
- Modules: group everything per feature/context and provide entrypoints/wiring. Keep core only for truly shared cross-cutting pieces.

## Minimal end-to-end demo (in-memory)
```python
repo = InMemoryNoteRepository()
create_note = CreateNote(repo)
list_notes = ListNotes(repo)

create_note.execute("First note")
print(list_notes.execute())
```

## Bank balance alert example (docs-only)
Not scaffolded—illustrative only. Shows per-layer files and imports.

`modules/banking/domain/entities.py`
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

`modules/banking/domain/ports.py`
```python
from typing import Protocol
from .entities import Account


class AccountRepository(Protocol):
    def get(self, account_id: str) -> Account | None: ...
    def save(self, account: Account) -> None: ...


class NotificationPort(Protocol):
    def send_balance_alert(self, to_email: str, current_balance: float, threshold: float) -> None: ...
```

`modules/banking/application/balance_alert.py`
```python
from .domain.entities import Account
from .domain.ports import AccountRepository, NotificationPort


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
```

`modules/banking/infrastructure/repositories.py`
```python
from ..domain.entities import Account
from ..domain.ports import AccountRepository


class InMemoryAccountRepository(AccountRepository):
    def __init__(self):
        self.items: dict[str, Account] = {}

    def get(self, account_id: str) -> Account | None:
        return self.items.get(account_id)

    def save(self, account: Account) -> None:
        self.items[account.id] = account
```

`modules/banking/infrastructure/notifications.py`
```python
from ..domain.ports import NotificationPort


class EmailNotificationAdapter(NotificationPort):
    def send_balance_alert(self, to_email: str, current_balance: float, threshold: float) -> None:
        print(f"Email -> {to_email}: balance ${current_balance:.2f} is below ${threshold:.2f}")
```

`modules/banking/main.py`
```python
from datetime import datetime
from .application.balance_alert import BalanceAlertService
from .infrastructure.notifications import EmailNotificationAdapter
from .infrastructure.repositories import InMemoryAccountRepository
from .domain.entities import Account


def run_demo() -> None:
    accounts = InMemoryAccountRepository()
    notifier = EmailNotificationAdapter()
    service = BalanceAlertService(accounts, notifier)

    accounts.save(Account(id="acc-123", owner_email="user@example.com", balance=49.0, updated_at=datetime.utcnow()))
    service.execute(account_id="acc-123", threshold=50.0)


if __name__ == "__main__":
    run_demo()
```
