"""Shared deterministic market-data fixtures."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from ai_trading_lab.data.contracts import Candle, Instrument, Timeframe


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


@pytest.fixture
def instrument_factory():  # type: ignore[no-untyped-def]
    """Create realistic linear-perpetual trading constraints."""

    def factory(symbol: str = "BTCUSDT", **changes: object) -> Instrument:
        base = {
            "symbol": symbol,
            "base_coin": symbol.removesuffix("USDT"),
            "quote_coin": "USDT",
            "settle_coin": "USDT",
            "status": "Trading",
            "contract_type": "LinearPerpetual",
            "launch_time": datetime(2020, 1, 1, tzinfo=UTC),
            "delivery_time": None,
            "tick_size": Decimal("0.1"),
            "min_price": Decimal("0.1"),
            "max_price": Decimal("1000000"),
            "quantity_step": Decimal("0.001"),
            "min_order_quantity": Decimal("0.001"),
            "max_order_quantity": Decimal("1000"),
            "min_notional": Decimal("1"),
            "min_leverage": Decimal("1"),
            "max_leverage": Decimal("100"),
            "leverage_step": Decimal("0.01"),
            "funding_interval_minutes": 480,
        }
        base.update(changes)
        return Instrument(**base)  # type: ignore[arg-type]

    return factory
