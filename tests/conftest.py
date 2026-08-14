"""Shared deterministic market-data fixtures."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from ai_trading_lab.data.contracts import Candle, Timeframe


@pytest.fixture
def candle_factory():  # type: ignore[no-untyped-def]
    """Create valid one-minute candles with overridable fields."""

    def factory(index: int = 0, **changes: object) -> Candle:
        base = {
            "symbol": "BTCUSDT",
            "timeframe": Timeframe.ONE_MINUTE,
            "open_time": datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=index),
            "open": Decimal("100"),
            "high": Decimal("102"),
            "low": Decimal("99"),
            "close": Decimal("101"),
            "volume": Decimal("10"),
            "turnover": Decimal("1005"),
        }
        base.update(changes)
        return Candle(**base)  # type: ignore[arg-type]

    return factory
