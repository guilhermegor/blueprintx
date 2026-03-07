# **DDD Service (ORM) — External API Calls**

How to integrate external APIs using the ports-and-adapters pattern with SQLAlchemy for persistence.

> **See also:** [Core concepts](../ddd-service-orm-db.md) · [Usage examples](ddd-orm-usage-examples.md) · [Bank balance alert](ddd-orm-bank-balance-alert.md)

---

## Overview

When fetching data from external services and persisting with SQLAlchemy:

| Layer | Responsibility |
|-------|----------------|
| **Domain** (`ports.py`) | Define interfaces for external data + persistence |
| **Infrastructure** | API adapters + SQLAlchemy repositories |
| **Application** (`use_cases.py`) | Orchestrate fetching and storing |

---

## Example: Stock Exchange Historical Data with Persistence

### Domain Layer

**`modules/market_data/domain/entities.py`**
```python
from dataclasses import dataclass
from datetime import date


@dataclass
class OHLCV:
    """Open-High-Low-Close-Volume candle."""
    id: str | None
    symbol: str
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int
```

**`modules/market_data/domain/ports.py`**
```python
from abc import ABC, abstractmethod
from datetime import date
from typing import Optional
from .entities import OHLCV


class StockDataPort(ABC):
    """Port for fetching historical market data from external APIs."""

    @abstractmethod
    def get_historical_data(self, symbol: str, start: date, end: date) -> list[OHLCV]:
        """Fetch historical OHLCV data for a symbol."""


class OHLCVRepository(ABC):
    """Port for persisting OHLCV data."""

    @abstractmethod
    def save(self, candle: OHLCV) -> OHLCV:
        """Persist a single candle."""

    @abstractmethod
    def save_many(self, candles: list[OHLCV]) -> list[OHLCV]:
        """Persist multiple candles."""

    @abstractmethod
    def get_by_symbol(self, symbol: str, start: date, end: date) -> list[OHLCV]:
        """Retrieve candles for a symbol within date range."""

    @abstractmethod
    def exists(self, symbol: str, candle_date: date) -> bool:
        """Check if a candle already exists."""
```

### Infrastructure Layer — SQLAlchemy Models

**`modules/market_data/infrastructure/models.py`**
```python
from datetime import date as date_type
from sqlalchemy import String, Date, Float, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from core.infrastructure.database import Base, generate_uuid


class OHLCVModel(Base):
    """SQLAlchemy model for OHLCV candles."""

    __tablename__ = "ohlcv_candles"
    __table_args__ = (
        UniqueConstraint("symbol", "date", name="uq_symbol_date"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    symbol: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    date: Mapped[date_type] = mapped_column(Date, nullable=False, index=True)
    open: Mapped[float] = mapped_column(Float, nullable=False)
    high: Mapped[float] = mapped_column(Float, nullable=False)
    low: Mapped[float] = mapped_column(Float, nullable=False)
    close: Mapped[float] = mapped_column(Float, nullable=False)
    volume: Mapped[int] = mapped_column(Integer, nullable=False)

    def to_entity(self) -> "OHLCV":
        from ..domain.entities import OHLCV
        return OHLCV(
            id=self.id,
            symbol=self.symbol,
            date=self.date,
            open=self.open,
            high=self.high,
            low=self.low,
            close=self.close,
            volume=self.volume,
        )

    @classmethod
    def from_entity(cls, entity: "OHLCV") -> "OHLCVModel":
        return cls(
            id=entity.id or generate_uuid(),
            symbol=entity.symbol,
            date=entity.date,
            open=entity.open,
            high=entity.high,
            low=entity.low,
            close=entity.close,
            volume=entity.volume,
        )
```

### Infrastructure Layer — Repository

**`modules/market_data/infrastructure/repositories.py`**
```python
from datetime import date
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, and_
from core.infrastructure.database import Repository
from .models import OHLCVModel
from ..domain.entities import OHLCV
from ..domain.ports import OHLCVRepository


class SQLAlchemyOHLCVRepository(OHLCVRepository, Repository):
    """SQLAlchemy implementation of OHLCV repository."""

    def __init__(self, session: Session):
        super().__init__(session)

    def save(self, candle: OHLCV) -> OHLCV:
        model = OHLCVModel.from_entity(candle)
        self.session.merge(model)  # merge handles insert or update
        self.session.flush()
        candle.id = model.id
        return candle

    def save_many(self, candles: list[OHLCV]) -> list[OHLCV]:
        for candle in candles:
            self.save(candle)
        return candles

    def get_by_symbol(self, symbol: str, start: date, end: date) -> list[OHLCV]:
        stmt = (
            select(OHLCVModel)
            .where(
                and_(
                    OHLCVModel.symbol == symbol,
                    OHLCVModel.date >= start,
                    OHLCVModel.date <= end,
                )
            )
            .order_by(OHLCVModel.date)
        )
        models = self.session.execute(stmt).scalars().all()
        return [m.to_entity() for m in models]

    def exists(self, symbol: str, candle_date: date) -> bool:
        stmt = select(OHLCVModel.id).where(
            and_(OHLCVModel.symbol == symbol, OHLCVModel.date == candle_date)
        )
        return self.session.execute(stmt).scalar() is not None
```

### Infrastructure Layer — API Adapter

**`modules/market_data/infrastructure/stock_api_adapter.py`**
```python
import requests
from datetime import date
from ..domain.entities import OHLCV
from ..domain.ports import StockDataPort


class AlphaVantageAdapter(StockDataPort):
    """Adapter for Alpha Vantage stock API."""

    def __init__(self, api_key: str):
        self._api_key = api_key
        self._base_url = "https://www.alphavantage.co/query"

    def get_historical_data(self, symbol: str, start: date, end: date) -> list[OHLCV]:
        params = {
            "function": "TIME_SERIES_DAILY",
            "symbol": symbol,
            "apikey": self._api_key,
            "outputsize": "full",
        }
        response = requests.get(self._base_url, params=params)
        response.raise_for_status()
        return self._parse_response(response.json(), symbol, start, end)

    def _parse_response(self, data: dict, symbol: str, start: date, end: date) -> list[OHLCV]:
        time_series = data.get("Time Series (Daily)", {})
        results = []
        for date_str, values in time_series.items():
            d = date.fromisoformat(date_str)
            if start <= d <= end:
                results.append(OHLCV(
                    id=None,  # Will be assigned on save
                    symbol=symbol,
                    date=d,
                    open=float(values["1. open"]),
                    high=float(values["2. high"]),
                    low=float(values["3. low"]),
                    close=float(values["4. close"]),
                    volume=int(values["5. volume"]),
                ))
        return sorted(results, key=lambda x: x.date)
```

### Application Layer

**`modules/market_data/application/use_cases.py`**
```python
from datetime import date
from ..domain.ports import StockDataPort, OHLCVRepository
from ..domain.entities import OHLCV


class FetchAndStoreHistoricalPrices:
    """Fetch historical data from API and persist to database."""

    def __init__(self, stock_api: StockDataPort, repository: OHLCVRepository):
        self._stock_api = stock_api
        self._repository = repository

    def execute(self, symbol: str, start: date, end: date) -> list[OHLCV]:
        """Fetch prices and store them, skipping existing records."""
        candles = self._stock_api.get_historical_data(symbol, start, end)
        
        new_candles = [
            c for c in candles
            if not self._repository.exists(symbol, c.date)
        ]
        
        if new_candles:
            self._repository.save_many(new_candles)
        
        return new_candles


class GetStoredPrices:
    """Retrieve historical prices from database."""

    def __init__(self, repository: OHLCVRepository):
        self._repository = repository

    def execute(self, symbol: str, start: date, end: date) -> list[OHLCV]:
        return self._repository.get_by_symbol(symbol, start, end)
```

### Wiring it together

**`modules/market_data/main.py`**
```python
import os
from datetime import date
from core.application import build_database_session
from .infrastructure.stock_api_adapter import AlphaVantageAdapter
from .infrastructure.repositories import SQLAlchemyOHLCVRepository
from .application.use_cases import FetchAndStoreHistoricalPrices, GetStoredPrices


def run_demo():
    api_key = os.getenv("ALPHA_VANTAGE_API_KEY", "demo")
    
    # Setup database
    db = build_database_session()
    db.create_tables()
    
    with db.session() as session:
        # Wire dependencies
        api_adapter = AlphaVantageAdapter(api_key)
        repository = SQLAlchemyOHLCVRepository(session)
        
        fetch_and_store = FetchAndStoreHistoricalPrices(api_adapter, repository)
        get_prices = GetStoredPrices(repository)
        
        # Fetch from API and store
        new_candles = fetch_and_store.execute(
            symbol="AAPL",
            start=date(2026, 1, 1),
            end=date(2026, 1, 31),
        )
        session.commit()
        print(f"Stored {len(new_candles)} new candles")
        
        # Retrieve from database
        stored = get_prices.execute("AAPL", date(2026, 1, 1), date(2026, 1, 31))
        for candle in stored:
            print(f"{candle.date}: O={candle.open:.2f} C={candle.close:.2f}")


if __name__ == "__main__":
    run_demo()
```

---

## Testing with SQLAlchemy

```python
import pytest
from unittest.mock import Mock
from datetime import date
from core.infrastructure.database import DatabaseSession
from modules.market_data.infrastructure.repositories import SQLAlchemyOHLCVRepository
from modules.market_data.application.use_cases import FetchAndStoreHistoricalPrices
from modules.market_data.domain.entities import OHLCV


@pytest.fixture
def db_session():
    db = DatabaseSession("sqlite:///:memory:")
    db.create_tables()
    with db.session() as session:
        yield session


def test_fetch_and_store_new_candles(db_session):
    # Mock the API adapter
    mock_api = Mock()
    mock_api.get_historical_data.return_value = [
        OHLCV(None, "AAPL", date(2026, 1, 15), 150.0, 155.0, 149.0, 154.0, 1000000)
    ]
    
    repo = SQLAlchemyOHLCVRepository(db_session)
    use_case = FetchAndStoreHistoricalPrices(mock_api, repo)
    
    result = use_case.execute("AAPL", date(2026, 1, 1), date(2026, 1, 31))
    db_session.commit()
    
    assert len(result) == 1
    assert result[0].symbol == "AAPL"
    
    # Verify it's in the database
    stored = repo.get_by_symbol("AAPL", date(2026, 1, 1), date(2026, 1, 31))
    assert len(stored) == 1


def test_skips_existing_candles(db_session):
    repo = SQLAlchemyOHLCVRepository(db_session)
    
    # Pre-populate database
    existing = OHLCV(None, "AAPL", date(2026, 1, 15), 150.0, 155.0, 149.0, 154.0, 1000000)
    repo.save(existing)
    db_session.commit()
    
    # Mock API returns same date
    mock_api = Mock()
    mock_api.get_historical_data.return_value = [
        OHLCV(None, "AAPL", date(2026, 1, 15), 151.0, 156.0, 150.0, 155.0, 2000000)
    ]
    
    use_case = FetchAndStoreHistoricalPrices(mock_api, repo)
    result = use_case.execute("AAPL", date(2026, 1, 1), date(2026, 1, 31))
    
    assert len(result) == 0  # Skipped because it exists
```

---

## Benefits of ORM Approach

| Benefit | Description |
|---------|-------------|
| **Type safety** | ORM models provide IDE autocompletion and type hints |
| **Migrations** | Easy to evolve schema with Alembic |
| **Relationships** | Define foreign keys and joins declaratively |
| **Query builder** | Complex queries without string concatenation |
| **Transaction safety** | Session handles rollback on errors |
