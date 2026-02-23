# **DDD Service — External API Calls**

How to integrate external APIs (stock exchanges, payment gateways, third-party services) using the ports-and-adapters pattern.

> **See also:** [Core concepts](../ddd-service.md) · [Usage examples](ddd-usage-examples.md) · [Bank balance alert](ddd-bank-balance-alert.md)

---

## Overview

When fetching data from external services, apply the same hexagonal pattern:

| Layer | Responsibility |
|-------|----------------|
| **Domain** (`ports.py`) | Define an interface describing *what* you need |
| **Infrastructure** | Implement the adapter that calls the external API |
| **Application** (`use_cases.py`) | Orchestrate by injecting the port |

---

## Example: Stock Exchange Historical Data

### Domain Layer

**`modules/market_data/domain/entities.py`**
```python
from dataclasses import dataclass
from datetime import date


@dataclass
class OHLCV:
    """Open-High-Low-Close-Volume candle."""
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
from .entities import OHLCV


class StockDataPort(ABC):
    """Port for fetching historical market data."""

    @abstractmethod
    def get_historical_data(self, symbol: str, start: date, end: date) -> list[OHLCV]:
        """Fetch historical OHLCV data for a symbol."""
```

### Infrastructure Layer

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
from ..domain.ports import StockDataPort
from ..domain.entities import OHLCV


class GetHistoricalPrices:
    def __init__(self, stock_data: StockDataPort):
        self._stock_data = stock_data

    def execute(self, symbol: str, start: date, end: date) -> list[OHLCV]:
        return self._stock_data.get_historical_data(symbol, start, end)
```

### Wiring it together

**`modules/market_data/main.py`**
```python
import os
from datetime import date
from .infrastructure.stock_api_adapter import AlphaVantageAdapter
from .application.use_cases import GetHistoricalPrices


def run_demo():
    api_key = os.getenv("ALPHA_VANTAGE_API_KEY", "demo")
    
    adapter = AlphaVantageAdapter(api_key)
    get_prices = GetHistoricalPrices(adapter)
    
    prices = get_prices.execute(
        symbol="AAPL",
        start=date(2026, 1, 1),
        end=date(2026, 1, 31),
    )
    
    for candle in prices:
        print(f"{candle.date}: O={candle.open:.2f} H={candle.high:.2f} L={candle.low:.2f} C={candle.close:.2f}")


if __name__ == "__main__":
    run_demo()
```

---

## Swapping providers

The beauty of this pattern — switch from Alpha Vantage to Yahoo Finance without touching use-cases:

```python
class YahooFinanceAdapter(StockDataPort):
    """Alternative adapter using Yahoo Finance."""

    def get_historical_data(self, symbol: str, start: date, end: date) -> list[OHLCV]:
        # Different API, same interface
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        df = ticker.history(start=start, end=end)
        return [
            OHLCV(
                symbol=symbol,
                date=idx.date(),
                open=row["Open"],
                high=row["High"],
                low=row["Low"],
                close=row["Close"],
                volume=int(row["Volume"]),
            )
            for idx, row in df.iterrows()
        ]
```

```python
# Swap with zero changes to use-case
adapter = YahooFinanceAdapter()  # instead of AlphaVantageAdapter
get_prices = GetHistoricalPrices(adapter)
```

---

## Testing with mocks

```python
import pytest
from unittest.mock import Mock
from datetime import date
from modules.market_data.application.use_cases import GetHistoricalPrices
from modules.market_data.domain.entities import OHLCV


def test_get_historical_prices():
    mock_adapter = Mock()
    mock_adapter.get_historical_data.return_value = [
        OHLCV("AAPL", date(2026, 1, 15), 150.0, 155.0, 149.0, 154.0, 1000000)
    ]
    
    use_case = GetHistoricalPrices(mock_adapter)
    result = use_case.execute("AAPL", date(2026, 1, 1), date(2026, 1, 31))
    
    assert len(result) == 1
    assert result[0].symbol == "AAPL"
    mock_adapter.get_historical_data.assert_called_once_with(
        "AAPL", date(2026, 1, 1), date(2026, 1, 31)
    )
```

---

## Benefits

| Benefit | Description |
|---------|-------------|
| **Isolation** | Domain stays pure and testable (no HTTP dependencies) |
| **Swappability** | Easy to switch providers (Alpha Vantage → Yahoo Finance → Bloomberg) |
| **Testability** | Mock the port in tests without hitting real APIs |
| **Resilience** | Add retries, caching, circuit breakers in the adapter without touching domain |
